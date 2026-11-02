"use client";

import { Check, Send, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

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
import type { Provider, RegisteredModel } from "@/core/models/types";
import { readChatStream, visibleText } from "@/core/projects/stream";
import type { ProjectDetail, ProjectMessage, ProjectResult } from "@/core/projects/types";
import { apiClient } from "@/lib/api";

const MODEL_SETTING = "chat_model";
const SUGGESTIONS = [
  "Fais-moi une roadmap pour ce projet",
  "Propose les agents dont j’aurais besoin",
];

const reference = (model: RegisteredModel) => `${model.provider_name}/${model.model_id}`;

function ProposalCard({
  message,
  onAnswer,
}: {
  message: ProjectMessage;
  onAnswer(action: "approve" | "reject"): void;
}) {
  const proposal = message.proposal!;
  return (
    <div className="proposal" data-status={message.proposal_status}>
      <p className="proposal-title">Proposition</p>
      {proposal.roadmap && (
        <>
          <p>
            <strong>Roadmap : {proposal.roadmap.title}</strong>
          </p>
          <ol>
            {proposal.roadmap.steps.map((step) => (
              <li key={step.title}>{step.title}</li>
            ))}
          </ol>
        </>
      )}
      {proposal.agents.length > 0 && (
        <>
          <p>
            <strong>Agents à créer</strong>
          </p>
          <ul>
            {proposal.agents.map((agent) => (
              <li key={agent.name}>
                {agent.name}
                {agent.role && ` : ${agent.role}`}
              </li>
            ))}
          </ul>
        </>
      )}
      {message.proposal_status === "pending" ? (
        <div className="proposal-actions">
          <Button size="sm" onClick={() => onAnswer("approve")}>
            <Check /> Valider
          </Button>
          <Button size="sm" variant="outline" onClick={() => onAnswer("reject")}>
            <X /> Refuser
          </Button>
        </div>
      ) : (
        <p className="muted">
          {message.proposal_status === "approved" ? "Validée et ajoutée aux résultats" : "Refusée"}
        </p>
      )}
    </div>
  );
}

function ResultCard({ result }: { result: ProjectResult }) {
  if (result.kind === "agent") {
    return (
      <div className="result-card">
        <span className="result-kind">Agent</span>
        <strong>{result.title}</strong>
        {typeof result.content.role === "string" && <span className="muted">{result.content.role}</span>}
      </div>
    );
  }
  const steps = (result.content.steps ?? []) as { title: string; detail: string }[];
  return (
    <div className="result-card">
      <span className="result-kind">Roadmap</span>
      <strong>{result.title}</strong>
      <ol>
        {steps.map((step) => (
          <li key={step.title}>
            {step.title}
            {step.detail && <p className="muted">{step.detail}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ProjectPage({ id }: { id: string }) {
  useAppearance();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [models, setModels] = useState<RegisteredModel[] | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [model, setModel] = useState("");
  const [input, setInput] = useState("");
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [streaming, setStreaming] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paidOk, setPaidOk] = useState(false);
  const [confirmPaid, setConfirmPaid] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  const reload = useCallback(async () => {
    setProject(await apiClient.getProject(id));
  }, [id]);

  useEffect(() => {
    apiClient.getProject(id).then(setProject, () => setError("Ce projet est introuvable."));
    void (async () => {
      const [available, saved, known] = await Promise.all([
        apiClient.listModels(),
        apiClient.getSetting(MODEL_SETTING),
        apiClient.listProviders(),
      ]);
      setModels(available);
      setProviders(known);
      const names = available.map(reference);
      setModel(names.includes(String(saved)) ? String(saved) : (names[0] ?? ""));
    })().catch(() => setModels([]));
  }, [id]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [project?.messages.length, streaming, pendingUser]);

  const selected = models?.find((item) => reference(item) === model);
  const isPaid = providers.find((item) => item.id === selected?.provider_id)?.paid ?? false;

  const send = async (content: string, allowPaid: boolean) => {
    setError(null);
    setPendingUser(content);
    setStreaming("");
    setInput("");
    let text = "";
    try {
      const response = await apiClient.chat(id, { content, model, allow_paid: allowPaid });
      await readChatStream(response, {
        onDelta(delta) {
          text += delta;
          setStreaming(visibleText(text));
        },
        onFailure: setError,
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
    await reload();
    setPendingUser(null);
    setStreaming(null);
  };

  const ask = (content: string) => {
    const text = content.trim();
    if (!text || streaming !== null || !model) return;
    if (isPaid && !paidOk) setConfirmPaid(text);
    else void send(text, isPaid);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    ask(input);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      ask(input);
    }
  };

  const answer = async (message: ProjectMessage, action: "approve" | "reject") => {
    try {
      setProject(await apiClient.answerProposal(id, message.id, action));
    } catch (cause) {
      setError(String(cause));
    }
  };

  return (
    <div className="app-page">
      <AppHeader>
        <span className="project-title">{project?.name}</span>
      </AppHeader>
      <main className="project-layout">
        <section className="chat" aria-label="Conversation">
          <div className="chat-log">
            {project?.messages.length === 0 && !pendingUser && (
              <div className="chat-empty">
                <h2>Par quoi commencer ?</h2>
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="suggestion"
                    disabled={!model}
                    onClick={() => ask(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            {project?.messages.map((message) => (
              <div key={message.id} className="message" data-role={message.role}>
                {message.content && <p>{message.content}</p>}
                {message.proposal && (
                  <ProposalCard
                    message={message}
                    onAnswer={(action) => void answer(message, action)}
                  />
                )}
              </div>
            ))}
            {pendingUser && (
              <div className="message" data-role="user">
                <p>{pendingUser}</p>
              </div>
            )}
            {streaming !== null && (
              <div className="message" data-role="assistant" aria-live="polite">
                <p>{streaming || "L’assistant réfléchit…"}</p>
              </div>
            )}
            {error && (
              <p className="field-error" role="alert">
                {error}
              </p>
            )}
            <div ref={end} />
          </div>
          {models?.length === 0 ? (
            <p className="chat-setup">
              Aucun modèle n’est configuré. <Link href="/settings">Ajouter un modèle</Link>
            </p>
          ) : (
            <form className="chat-input" onSubmit={submit}>
              <textarea
                aria-label="Ton message"
                placeholder="Écris ton message…"
                rows={2}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={onKeyDown}
              />
              <div className="chat-controls">
                <select
                  aria-label="Modèle"
                  value={model}
                  onChange={(event) => {
                    setModel(event.target.value);
                    void apiClient.putSetting(MODEL_SETTING, event.target.value);
                  }}
                >
                  {models?.map((item) => (
                    <option key={item.id} value={reference(item)}>
                      {item.model_id}
                    </option>
                  ))}
                </select>
                <Button type="submit" size="sm" disabled={streaming !== null || !input.trim()}>
                  <Send /> Envoyer
                </Button>
              </div>
            </form>
          )}
        </section>
        <aside className="results" aria-label="Résultats">
          <h2>Résultats</h2>
          {project?.results.length === 0 && (
            <p className="muted">Ce que tu valides dans la conversation apparaîtra ici.</p>
          )}
          {project?.results.map((result) => <ResultCard key={result.id} result={result} />)}
        </aside>
      </main>
      <Dialog
        open={confirmPaid !== null}
        onOpenChange={(open) => !open && setConfirmPaid(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ce modèle est payant</DialogTitle>
          </DialogHeader>
          <p className="muted">Les messages de cette page seront facturés sur ton compte.</p>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setConfirmPaid(null)}>
              Annuler
            </Button>
            <Button
              size="sm"
              onClick={() => {
                const text = confirmPaid;
                setPaidOk(true);
                setConfirmPaid(null);
                if (text) void send(text, true);
              }}
            >
              Continuer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
