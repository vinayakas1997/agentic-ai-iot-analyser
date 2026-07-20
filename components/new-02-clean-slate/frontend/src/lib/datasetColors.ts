export const DATASET_COLORS = [
  { chip: "bg-ic-teal-soft/20 text-ic-teal border-ic-teal/20" },
  { chip: "bg-ic-amber-soft/20 text-ic-amber border-ic-amber/20" },
  { chip: "bg-ic-violet-soft/20 text-ic-violet border-ic-violet/20" },
  { chip: "bg-ic-blue-soft/20 text-ic-blue border-ic-blue/20" },
  { chip: "bg-ic-coral-soft/20 text-ic-coral border-ic-coral/20" },
  { chip: "bg-ic-red-soft/20 text-ic-red border-ic-red/20" },
  { chip: "bg-ic-pink-soft/20 text-ic-pink border-ic-pink/20" },
  { chip: "bg-ic-orange-soft/20 text-ic-orange border-ic-orange/20" },
  { chip: "bg-ic-cyan-soft/20 text-ic-cyan border-ic-cyan/20" },
  { chip: "bg-ic-lime-soft/20 text-ic-lime border-ic-lime/20" },
];

export function datasetColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = ((hash << 5) - hash) + name.charCodeAt(i);
  return DATASET_COLORS[Math.abs(hash) % DATASET_COLORS.length].chip;
}
