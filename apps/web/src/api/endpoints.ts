import { getJson, postJson } from "./client";
import type {
  DisplayRequest,
  DisplayResponse,
  ServerConfig,
  TriggerRequest,
  TriggerResponse,
} from "./types";

export const EXPORT_URL = "/api/export";

export function fetchConfig(): Promise<ServerConfig> {
  return getJson<ServerConfig>("/api/config");
}

export function postTrigger(
  body: TriggerRequest,
  token: string,
): Promise<{ data: TriggerResponse; httpStatus: number }> {
  return postJson<TriggerRequest, TriggerResponse>("/api/trigger", body, token);
}

export function postDisplay(
  body: DisplayRequest,
  token: string,
): Promise<{ data: DisplayResponse; httpStatus: number }> {
  return postJson<DisplayRequest, DisplayResponse>("/api/display", body, token);
}
