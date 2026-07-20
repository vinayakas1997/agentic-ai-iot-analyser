import { monoClass } from "../lib/styles";

export function DatasetColumns({ columns }: { columns: { name: string; datatype: string; meaning?: string }[] }) {
  return (
    <div className="rounded-lg border border-border/50 bg-surface-2 overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] font-semibold tracking-wider uppercase text-tertiary bg-black/[0.08]">
            <th className="text-left py-1.5 px-2.5 w-[30%]">Name</th>
            <th className="text-left py-1.5 px-2 w-[16%]">Type</th>
            <th className="text-left py-1.5 px-2.5">Description</th>
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
              <td className="py-1.5 px-2.5 text-muted">{col.meaning || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
