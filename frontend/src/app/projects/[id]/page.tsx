import { Suspense } from "react";

import { ProjectPage } from "@/components/home/project-page";

async function Loaded({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProjectPage id={id} />;
}

export default function Project({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense>
      <Loaded params={params} />
    </Suspense>
  );
}
