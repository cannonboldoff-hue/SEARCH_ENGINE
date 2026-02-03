import {
  Building2,
  Code2,
  FlaskConical,
  Rocket,
  TrendingUp,
} from "lucide-react";

type CardTypeIconProps = {
  tags: string[];
  title: string | null;
  className?: string;
};

export function CardTypeIcon({ tags, title, className }: CardTypeIconProps) {
  const t = (tags || []).map((x) => x.toLowerCase()).join(" ");
  const tit = (title || "").toLowerCase();
  if (tit.includes("research") || t.includes("research"))
    return <FlaskConical className={`h-4 w-4 text-violet-400 ${className ?? ""}`} />;
  if (tit.includes("startup") || t.includes("startup"))
    return <Rocket className={`h-4 w-4 text-amber-400 ${className ?? ""}`} />;
  if (tit.includes("quant") || t.includes("quant") || tit.includes("finance"))
    return <TrendingUp className={`h-4 w-4 text-emerald-400 ${className ?? ""}`} />;
  if (tit.includes("open-source") || t.includes("open-source") || t.includes("opensource"))
    return <Code2 className={`h-4 w-4 text-blue-400 ${className ?? ""}`} />;
  return <Building2 className={`h-4 w-4 text-muted-foreground ${className ?? ""}`} />;
}
