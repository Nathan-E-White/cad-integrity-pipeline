import { mount, unmount } from "svelte";
import Demo from "./Demo.svelte";
const target = document.getElementById("app");
if (!target) throw new Error("Missing #app mount element");
const app = mount(Demo, { target });
if (import.meta.hot) import.meta.hot.dispose(() => { void unmount(app); });
