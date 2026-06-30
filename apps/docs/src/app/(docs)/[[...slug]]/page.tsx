import { notFound } from "next/navigation";
import {
  PageArticle,
  PageRoot,
  PageTOC,
  PageTOCItems,
  PageTOCTitle,
} from "fumadocs-ui/layouts/docs/page";
import defaultMdxComponents from "fumadocs-ui/mdx";
import { source } from "@/lib/source";

export default async function Page(props: {
  params: Promise<{ slug?: string[] }>;
}) {
  const params = await props.params;
  const page = source.getPage(params.slug);

  if (!page) notFound();

  const MDX = page.data.body;

  return (
    <PageRoot toc={{ toc: page.data.toc }}>
      <PageArticle className="w-[calc(100vw-2rem)] max-w-4xl overflow-hidden pb-24 [overflow-wrap:anywhere] md:w-full md:pb-32 [&_p]:whitespace-normal">
        <p className="mb-4 text-sm font-semibold text-nb-primary">Visão geral</p>
        <h1 className="mb-3 text-4xl font-bold tracking-normal text-nb-text md:text-5xl">
          {page.data.title}
        </h1>
        {page.data.description && (
          <p className="mb-10 text-lg leading-8 text-nb-secondary md:text-xl">
            {page.data.description}
          </p>
        )}
        <MDX components={defaultMdxComponents} />
      </PageArticle>
      <PageTOC>
        <PageTOCTitle>Nesta página</PageTOCTitle>
        <PageTOCItems />
      </PageTOC>
    </PageRoot>
  );
}

export function generateStaticParams() {
  return source.generateParams();
}

export async function generateMetadata(props: {
  params: Promise<{ slug?: string[] }>;
}) {
  const params = await props.params;
  const page = source.getPage(params.slug);

  if (!page) notFound();

  return {
    title: page.data.title,
    description: page.data.description,
  };
}
