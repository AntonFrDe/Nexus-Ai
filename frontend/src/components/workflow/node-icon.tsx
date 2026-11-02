import { Box, icons } from "lucide-react";

const pascalCase = (name: string) =>
  name.replace(/(^|-)([a-z0-9])/g, (_, __, letter: string) => letter.toUpperCase());

/** Catalog icons are data, so they are resolved by name rather than imported. */
export function NodeIcon({ name, className }: { name: string; className?: string }) {
  const Icon = icons[pascalCase(name) as keyof typeof icons] ?? Box;
  return <Icon className={className} />;
}
