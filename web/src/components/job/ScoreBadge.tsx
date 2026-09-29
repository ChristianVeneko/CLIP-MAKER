export function ScoreBadge({ score }: { score: number }) {
  const tone = score >= 80 ? "high" : score >= 60 ? "mid" : "low";
  return (
    <span className={`score is-${tone}`} title="Puntuación de viralidad">
      <span aria-hidden>🔥</span> {Math.round(score)}
    </span>
  );
}
