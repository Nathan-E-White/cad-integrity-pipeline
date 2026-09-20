// Nitro 3/H3 2 example. Keep your application's existing Nitro version and route convention.
import { defineHandler } from "nitro";
import { demoModelHandler } from "../../../../demo-service";

export default defineHandler((event) => demoModelHandler(event.req));
