import { monoClass } from "../lib/styles";
import { useT } from "../lib/i18n";

export function DatasetColumns({ columns }: { columns: { name: string; datatype: string; meaning?: string }[] }) {
  const t = useT();
  return (
    <div className="rounded-lg border border-border/40 bg-gradient-to-b from-black/[0.04] to-transparent overflow-hidden shadow-[inset_0_1px_2px_rgba(0,0,0,0.3)]">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] font-semibold tracking-wider uppercase text-tertiary bg-black/[0.08]">
            <th className="text-left py-1.5 px-2.5 w-[30%]">{t("common.name")}</th>
            <th className="text-left py-1.5 px-2 w-[16%]">{t("common.type")}</th>
            <th className="text-left py-1.5 px-2.5">{t("common.description")}</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => (
            <tr key={col.name} className="border-t border-border/20">
              <td className={`${monoClass} py-1.5 px-2.5 text-text font-medium`}>{col.name}</td>
              <td className="py-1.5 px-2">
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-surface-1 text-muted border border-border/30 whitespace-nowrap">
                  {col.datatype}
                </span>
              </td>
              <td className="py-1.5 px-2.5 text-muted whitespace-normal break-words">{col.meaning || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
