"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { AppHeader } from "@/components/home/app-header";
import { useAppearance } from "@/components/home/use-appearance";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { ProjectSummary } from "@/core/projects/types";
import { apiClient } from "@/lib/api";

function plural(count: number, word: string) {
  return `${count} ${word}${count > 1 ? "s" : ""}`;
}

export function ProjectsHome() {
  useAppearance();
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<ProjectSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      apiClient.listProjects().then(
        (items) => {
          setProjects(items);
          setError(null);
        },
        () => setError("NEXUS ne répond pas. Vérifie que le backend est lancé avec make backend."),
      ),
    [],
  );

  useEffect(() => {
    let alive = true;
    apiClient.listProjects().then(
      (items) => alive && setProjects(items),
      () =>
        alive &&
        setError("NEXUS ne répond pas. Vérifie que le backend est lancé avec make backend."),
    );
    return () => {
      alive = false;
    };
  }, []);

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const project = await apiClient.createProject(
      String(form.get("name")).trim(),
      String(form.get("description")).trim(),
    );
    router.push(`/projects/${project.id}`);
  };

  return (
    <div className="app-page">
      <AppHeader />
      <main className="home">
        <div className="home-head">
          <h1>Tes projets</h1>
          <Button onClick={() => setCreating(true)}>
            <Plus /> Nouveau projet
          </Button>
        </div>
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        {projects?.length === 0 && (
          <div className="home-empty">
            <h2>Commence par un projet</h2>
            <p>Décris ce que tu veux faire, et l’assistant t’aide à construire une roadmap et des agents.</p>
            <Button onClick={() => setCreating(true)}>Créer mon premier projet</Button>
          </div>
        )}
        <ul className="project-grid">
          {projects?.map((project) => (
            <li key={project.id} className="project-card">
              <Link href={`/projects/${project.id}`}>
                <h2>{project.name}</h2>
                {project.description && <p>{project.description}</p>}
                <span className="project-meta">
                  {plural(project.messages, "message")} · {plural(project.results, "résultat")} ·{" "}
                  {new Date(project.updated_at).toLocaleDateString("fr-FR")}
                </span>
              </Link>
              <button
                type="button"
                className="icon-button project-delete"
                aria-label={`Supprimer ${project.name}`}
                onClick={() => setDeleting(project)}
              >
                <Trash2 className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      </main>
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nouveau projet</DialogTitle>
          </DialogHeader>
          <form onSubmit={(event) => void create(event)} className="dialog-form">
            <label>
              Nom
              <Input name="name" required maxLength={120} autoFocus />
            </label>
            <label>
              Description (facultatif)
              <Input name="description" maxLength={2000} />
            </label>
            <DialogFooter>
              <Button type="submit" size="sm">
                Créer
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Supprimer « {deleting?.name} » ?</DialogTitle>
          </DialogHeader>
          <p className="muted">La conversation et les résultats seront perdus. Les agents créés restent disponibles.</p>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setDeleting(null)}>
              Annuler
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                if (deleting) void apiClient.deleteProject(deleting.id).then(load);
                setDeleting(null);
              }}
            >
              Supprimer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
