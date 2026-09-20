// Reference configuration when the project root is the current working directory.
// Merge the relevant setting into an existing application; do not replace its configuration.
import { defineConfig } from "nitro";

export default defineConfig({ serverDir: "./examples/nitro" });
