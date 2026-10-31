"""Original silent, deterministic scenes; labels never enter model prompts."""

from dataclasses import dataclass
import io

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

from experiments.realtime_video.provider import Frame


@dataclass(frozen=True)
class Case:
    name: str
    expected: str
    evidence_sequences: tuple
    description: str
    images: tuple


def _scene(*, red=1, health=100, popup=False, ball_x=400, small=0):
    image = Image.new("RGB", (1280, 720), "#15202b")
    draw = ImageDraw.Draw(image)
    font = lambda size: ImageFont.load_default(size=size)
    draw.rectangle((0, 0, 1280, 160), fill="#202d3d")
    draw.text((50, 25), "ARENA", fill="#eeeeee", font=font(34))
    draw.text((330, 30), "BLUE 3", fill="#5faaff", font=font(70))
    draw.text((790, 30), f"RED {red}", fill="#ff7070", font=font(70))
    draw.rectangle((80, 205, 1200, 560), outline="#334861", width=5)
    draw.line((640, 205, 640, 560), fill="#334861", width=3)
    draw.ellipse((ball_x-35, 350, ball_x+35, 420), fill="#f4d987")
    draw.text((80, 600), f"HP {health}", fill="white", font=font(34))
    draw.rectangle((270, 605, 1170, 650), fill="#38282f")
    draw.rectangle((270, 605, 270+9*health, 650), fill="#6dc5a4" if health>30 else "#e35e63")
    draw.text((1050, 170), f"POINTS {small}", fill="white", font=font(24))
    if popup:
        draw.rectangle((350, 270, 930, 500), fill="#942f3c", outline="#ffd5d5", width=6)
        draw.text((415, 325), "DEFEAT", fill="white", font=font(90))
    result = io.BytesIO()
    image.save(result, format="JPEG", quality=72)
    image.close()
    return result.getvalue()


def cases():
    base = _scene()
    return (
        Case("still", "WAIT", (), "Unchanging scoreboard", (base,)*6),
        Case("lead_change", "REACT", (4, 5, 6), "RED 1 to 4 overtakes BLUE 3",
             tuple(_scene(red=1 if index<3 else 4) for index in range(6))),
        Case("health_drop", "REACT", (4, 5, 6), "HP 100 to 20",
             tuple(_scene(health=100 if index<3 else 20) for index in range(6))),
        Case("transient", "REACT", (3, 4), "DEFEAT appears only in the middle",
             tuple(_scene(popup=index in (2, 3)) for index in range(6))),
        Case("motion_only", "WAIT", (), "Moving shape without score or health change",
             tuple(_scene(ball_x=280+120*index) for index in range(6))),
        Case("small_score", "REACT", (4, 5, 6), "Small POINTS counter 0 to 1",
             tuple(_scene(small=0 if index<3 else 1) for index in range(6))),
    )


def difference(left, right):
    with Image.open(io.BytesIO(left)) as a, Image.open(io.BytesIO(right)) as b:
        a = a.convert("RGB").resize((160, 90))
        b = b.convert("RGB").resize((160, 90))
        return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / (3*255)


def select(case, policy):
    if policy == "six":
        return tuple(range(6)), None
    if policy == "endpoints":
        return (0, 5), None
    if policy != "change":
        raise ValueError("Unknown frame policy")
    changes = [difference(case.images[index-1], case.images[index]) for index in range(1, 6)]
    maximum = max(changes)
    if maximum < .0005:
        return (), maximum
    index = changes.index(maximum)
    return (index, index+1), maximum


def model_frames(case, indices, now):
    # Preserve source order and relative ages, including the middle-only event.
    return [Frame(index+1, now-(5-index), case.images[index]) for index in indices]


def write_fixtures(directory, values):
    """Write reviewable originals and a contact sheet; no borrowed media."""
    directory.mkdir(parents=True, exist_ok=True)
    contact = Image.new("RGB", (6*240, len(values)*170), "white")
    draw = ImageDraw.Draw(contact)
    for row, case in enumerate(values):
        folder = directory / case.name
        folder.mkdir()
        for column, data in enumerate(case.images):
            (folder / f"{column+1:02d}.jpg").write_bytes(data)
            with Image.open(io.BytesIO(data)) as image:
                contact.paste(image.resize((240, 135)), (column*240, row*170+30))
        draw.text((5, row*170+5), f"{case.name}: {case.description}", fill="black", font_size=17)
    contact.save(directory / "contact_sheet.jpg")
    contact.close()


def scheduling_probe(interval, cooldown_before_call):
    """Offline deterministic call-count probe, not an AI quality benchmark."""
    calls, shown, suppressed, skips = 0, [], 0, 0
    now, last_chat = interval, float("-inf")
    while now < 60:
        if cooldown_before_call and now-last_chat < 8:
            skips += 1
            now += interval
            continue
        calls += 1
        now += 1.5  # Explicit assumed inference duration, not measured latency.
        if now >= 60:
            break
        if now-last_chat < 8:
            suppressed += 1
        else:
            shown.append(now)
            last_chat = now
        now += interval
    return {"calls": calls, "displayed": len(shown), "suppressed_after_paid_call": suppressed,
            "skipped_before_call": skips, "display_times": shown}
