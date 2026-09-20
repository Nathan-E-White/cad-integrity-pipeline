import { mount } from "svelte";
import Demo from "./Demo.svelte";
const target = document.getElementById("app");
if (!target) throw new Error("Missing #app mount element");
mount(Demo, { target });
