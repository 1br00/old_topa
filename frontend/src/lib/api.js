import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export function formatErr(err) {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || "Something went wrong.";
  if (typeof d === "string") return d;
  if (Array.isArray(d))
    return d.map((e) => (e?.msg ? e.msg : JSON.stringify(e))).join(" ");
  if (d?.msg) return d.msg;
  return JSON.stringify(d);
}
