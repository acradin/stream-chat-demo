"""Rasterize original Figma vectors/masks using Edge; no runtime browser required."""
import base64
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'apps/assets/figma'


def data(name):
    path = ASSETS / name
    mime = 'image/svg+xml' if path.suffix == '.svg' else 'image/png'
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()


def main():
    browser = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
    if not browser.is_file():
        raise SystemExit('Asset conversion requires Edge on Windows; generated PNGs are already bundled for every OS.')
    output = ROOT / 'build/figma-v2'
    output.mkdir(parents=True,exist_ok=True)
    boxes, html = {}, ['<!doctype html><style>html,body{margin:0;background:transparent}div,img{position:absolute}img{max-width:none}</style>']
    # Figma Persona instance geometry, including original image crop and mask offsets.
    personas = [
        ('witty',0,0,51,48,1,-2,162.67,169.44,-32,-36.11),
        ('analyst',0,3,50,43,1,-5,158.62,187.76,-29.31,-44.9),
        ('coach',1,3,48,48*655/712,0,-5,176.12,191.45,-38.34,-46.11),
        ('reaction',0,3,50,50*70/79,1,-5,165.82,187.14,-32.91,-42.86),
        ('chatter',0,0,50,50*51/52,1,-2,190.38,194.12,-46.15,-45.1),
        ('supporter',-1,1,51,48,2,-3,172.55,183.33,-35.29,-41.67)]
    mask = data('v2-source-persona-mask.svg')
    for index,(name,x,y,w,h,mx,my,iw,ih,ix,iy) in enumerate(personas):
        left = index*100
        html.append(f'<div style="left:{left}px;top:0;width:51px;height:48px"><div style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;mask:url({mask}) {mx}px {my}px / 50px 50px no-repeat;overflow:hidden"><img src="{data("v2-source-persona-"+name+".png")}" style="left:{ix}%;top:{iy}%;width:{iw}%;height:{ih}%"></div></div>')
        boxes['persona-'+name] = (left,0,left+51,48)
    import xml.etree.ElementTree as ET
    for index,name in enumerate(('orb-face','settings','crown','arrow','edit','wordmark','welcome-face','header')):
        filename = 'v2-header.svg' if name=='header' else 'v2-source-'+name+'.svg'
        node = ET.parse(ASSETS / filename).getroot()
        width,height = round(float(node.attrib['width'])),round(float(node.attrib['height']))
        x,y = index*120,160
        html.append(f'<img src="{data(filename)}" style="left:{x}px;top:{y}px;width:{width}px;height:{height}px">')
        boxes[name] = (x,y,x+width,y+height)
    page = output / 'assets.html'
    page.write_text('\n'.join(html),encoding='utf-8')
    for scale in (1,3):
        suffix = '' if scale == 1 else '@3x'
        with tempfile.TemporaryDirectory(prefix='edge-assets-',dir=output) as profile:
            subprocess.run([str(browser),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
                            '--force-device-scale-factor='+str(scale),'--default-background-color=00000000',
                            '--user-data-dir='+profile,'--window-size=1100,400','--hide-scrollbars','--virtual-time-budget=1000',
                            '--screenshot='+str(output/'assets.png'),page.as_uri()],check=True,capture_output=True,timeout=40)
        with Image.open(output/'assets.png') as image:
            for name,box in boxes.items():
                image.crop(tuple(round(value*scale) for value in box)).save(ASSETS / ('v2-'+name+suffix+'.png'))
        # Frame 55 uses the same original Paytone wordmark below the exported face.
        with Image.open(ASSETS/('v2-welcome-face'+suffix+'.png')) as face, Image.open(ASSETS/('v2-wordmark'+suffix+'.png')) as wordmark:
            logo = Image.new('RGBA',(99*scale,118*scale))
            logo.alpha_composite(face,(0,0))
            logo.alpha_composite(wordmark,((99*scale-wordmark.width)//2,83*scale))
            logo.save(ASSETS/('v2-welcome-logo'+suffix+'.png'))
    import hashlib
    manifest = [{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':list(Image.open(p).size)}
                for p in sorted(ASSETS.glob('v2-*.png'))]
    (ASSETS/'v2-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Figma assets rasterized with transparent backgrounds.')


if __name__ == '__main__':
    main()
