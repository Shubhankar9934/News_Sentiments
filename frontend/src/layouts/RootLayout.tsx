import { Outlet } from "react-router-dom";
import { useEffect } from "react";
import { useThemeStore } from "@/store/theme";

export function RootLayout() {
  const theme = useThemeStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return (
    <div className="min-h-dvh">
      <Outlet />
    </div>
  );
}
