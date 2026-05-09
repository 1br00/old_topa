import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { CheckCircle, Crown } from "@phosphor-icons/react";

/**
 * PlanCard — replicates the screenshot layout:
 * - Coloured top stripe (plan.color)
 * - Optional "MOST POPULAR" / section pill
 * - Big price + period
 * - Optional savings + monthly equivalent
 * - Section title ("Includes everything from PRO plus:")
 * - Feature list with green check pills
 * - LIMITS table
 * - Coloured "Select X" CTA at bottom
 */
export default function PlanCard({ plan, current = false, onClick, ctaLabel, secondaryAction, compact = false }) {
  const color = plan.color || "#4da3ff";
  const popular = plan.popular;
  const popularLabel = plan.popular_label || "MOST POPULAR";
  const ctaText = ctaLabel || `Select ${plan.name}`;

  return (
    <div
      data-testid={`plan-card-${plan.id}`}
      className="bg-[#121212] border border-white/10 relative overflow-hidden flex flex-col h-full"
    >
      {/* coloured top stripe */}
      <div className="h-1" style={{ background: color }} />

      {/* popular ribbon */}
      {popular && (
        <div className="px-6 pt-4">
          <span
            className="inline-block px-3 py-1 text-[10px] font-mono font-bold tracking-widest"
            style={{ background: `${color}26`, color: color, border: `1px solid ${color}66` }}
          >
            {popularLabel}
          </span>
        </div>
      )}

      <div className="px-6 pt-4 pb-2">
        <h3 className="font-mono font-bold text-2xl tracking-tight uppercase" style={{ color: color }}>
          {plan.name}
        </h3>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-4xl font-mono font-bold text-white">${plan.price}</span>
          <span className="text-sm text-[#a0a6ad] font-mono">/{plan.period}</span>
        </div>
        {plan.monthly_equiv && (
          <p className="text-xs text-[#a0a6ad] font-mono mt-1">{plan.monthly_equiv}</p>
        )}
        {plan.savings && (
          <div className="mt-3 px-3 py-2 text-[11px] font-mono text-[#00d4aa]" style={{ background: "rgba(0,212,170,0.07)", border: "1px solid rgba(0,212,170,0.18)" }}>
            {plan.savings}
          </div>
        )}
      </div>

      {/* Section title */}
      {plan.section_title && (
        <div className="px-6 py-2 text-[11px] font-mono text-[#a0a6ad] uppercase tracking-wider border-y border-white/5 bg-white/[0.02]">
          {plan.section_title}
        </div>
      )}

      {/* Features */}
      <ul className="px-6 py-4 space-y-2 flex-1">
        {plan.features.map((f, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-[#e8eaed] font-mono">
            <CheckCircle size={14} weight="fill" className="text-[#00d4aa] flex-shrink-0" />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      {/* Limits table */}
      <div className="mx-6 mb-4 border border-white/8">
        <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest text-[#737373] border-b border-white/8 bg-white/[0.02]">
          Limits
        </div>
        <div className="px-3 py-2">
          {Object.entries(plan.limits || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between text-xs font-mono py-1">
              <span className="text-[#a0a6ad]">{k}</span>
              <span className="text-white font-semibold">{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="px-6 pb-6 space-y-2">
        {current ? (
          <button
            disabled
            data-testid={`plan-cta-${plan.id}-current`}
            className="w-full py-3 font-mono font-bold text-sm tracking-wider uppercase border border-white/10 text-[#737373] bg-white/[0.03] cursor-not-allowed"
          >
            <Crown size={14} weight="duotone" className="inline mr-2" />
            Current plan
          </button>
        ) : (
          <button
            onClick={onClick}
            data-testid={`plan-cta-${plan.id}`}
            className="w-full py-3 font-mono font-bold text-sm tracking-wider uppercase text-white transition-all hover:brightness-110 active:scale-[0.98]"
            style={{ background: color }}
          >
            {ctaText}
          </button>
        )}
        {secondaryAction}
      </div>
    </div>
  );
}
