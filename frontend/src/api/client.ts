import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { toast } from "sonner";

const baseURL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "/api/v1";

export const apiClient = axios.create({
  baseURL,
  timeout: 120_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (error: AxiosError<{ detail?: unknown }>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? "Validation error"
          : error.message;

    // When axios sees no `error.response`, the request never received headers
    // (server overload, request aborted on navigation, true CORS misconfig,
    // or a true network error). Chrome reports all of these as "blocked by
    // CORS policy" in DevTools — surface a clearer message in the UI.
    const isNetworkLike =
      !error.response &&
      (error.code === "ERR_NETWORK" ||
        error.code === "ECONNABORTED" ||
        error.code === "ERR_CANCELED" ||
        error.message === "Network Error");

    if (status === 429) {
      // Polling endpoints may briefly hit rate limits; callers handle retries.
    } else if (status && status >= 500) {
      toast.error("Server error — try again shortly.");
    } else if (status === 401) {
      toast.error("Unauthorized");
    } else if (isNetworkLike) {
      // Quiet during navigation-cancellations: ERR_CANCELED is fired when
      // an unmounting component aborts the request. Show a toast only for
      // genuine network errors.
      if (error.code !== "ERR_CANCELED") {
        toast.error(
          "Backend unreachable — check that the API is running on http://localhost:8000.",
        );
      }
    } else {
      toast.error(message);
    }
    return Promise.reject(error);
  }
);
