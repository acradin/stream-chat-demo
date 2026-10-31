import { ApiError } from "./types";

// 모든 요청은 same-origin 의 /api/* 로 간다. Vite dev 프록시가 백엔드로 전달한다.
// 배포 시에도 정적 파일을 백엔드와 같은 origin 에서 서빙하면 그대로 동작한다.

async function parseJson<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(
      "서버 응답을 읽지 못했어요. 실행 터미널을 확인해 주세요.",
      response.status,
    );
  }
}

export async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "GET",
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError("백엔드 서버에 연결하지 못했어요.");
  }
  const data = await parseJson<T>(response);
  if (!response.ok) {
    throw new ApiError("서버가 요청을 거부했어요.", response.status);
  }
  return data;
}

/**
 * POST 요청. 토큰 헤더를 자동 주입한다.
 * 업무 상태가 200 이 아닌 코드로 올 수도 있으므로 httpStatus 를 함께 돌려준다.
 * 호출부에서 응답 본문의 status 필드로 최종 분기한다.
 */
export async function postJson<TReq, TRes>(
  path: string,
  body: TReq,
  token: string,
): Promise<{ data: TRes; httpStatus: number }> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Demo-Token": token,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("요청 중 연결이 끊겼어요. 자동으로 재시도하지 않습니다.");
  }

  // 400(입력 오류) / 403(토큰·origin 거절)은 본문이 있더라도 명확히 구분한다.
  if (response.status === 403) {
    throw new ApiError("로컬 접근이 거부됐어요 (토큰/origin).", 403);
  }
  if (response.status === 400) {
    const data = await parseJson<{ error?: string }>(response);
    throw new ApiError(data.error || "요청 형식이 올바르지 않아요.", 400);
  }

  const data = await parseJson<TRes>(response);
  return { data, httpStatus: response.status };
}
