import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { WorkbenchPrototype } from "./WorkbenchPrototype";

const params = new URLSearchParams(window.location.search);
const root = createRoot(document.getElementById("root")!);

root.render(
  <React.StrictMode>
    {params.get("view") === "live" ? <App /> : <WorkbenchPrototype />}
  </React.StrictMode>,
);
