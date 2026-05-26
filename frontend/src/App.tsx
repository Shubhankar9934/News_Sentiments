import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { RootLayout } from "@/layouts/RootLayout";
import { DashboardPage } from "@/pages/DashboardPage";
import { ReportPage } from "@/pages/ReportPage";
import { WatchlistGridPage } from "@/pages/WatchlistGridPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <WatchlistGridPage /> },
      { path: "report/:ticker", element: <ReportPage /> },
      { path: "workbench", element: <DashboardPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  );
}
