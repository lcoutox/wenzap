import { docs } from "collections";
import { loader } from "fumadocs-core/source";

const docsSource = docs.toFumadocsSource();
const docsFiles =
  typeof (docsSource.files as unknown) === "function"
    ? (
        docsSource.files as unknown as () => typeof docsSource.files
      )()
    : docsSource.files;

export const source = loader({
  baseUrl: "",
  source: {
    ...docsSource,
    files: docsFiles,
  } as unknown as typeof docsSource,
});
