import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import { initMotion } from "./lib/motion";

initMotion();
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
