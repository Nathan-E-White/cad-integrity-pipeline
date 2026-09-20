import { makeDemoDocument } from "../../src/demo/fixture";
import { createModelHandler } from "../../src/server/model-handler";

// Explicitly public SYNTHETIC demonstration only. No uploaded/private documents are served here.
export const demoModelHandler = createModelHandler({
  authorize: async ({ id }) => id === "synthetic-box-assembly",
  load: async ({ revision }) => revision === "1" ? makeDemoDocument() : null,
  onError: (error) => console.error("Synthetic model endpoint failed", error),
});
