import { BarChart3, Code2, Database } from 'lucide-react';
import { formatText } from '../../utils/format';

type Reference = {
  id: string;
  type: string;
  description: string;
  source: string;
};

type ReferencesProps = {
  references: Reference[];
};

const TYPE_ICONS: Record<string, typeof Database> = {
  query: Code2,
  column: Database,
  profile: BarChart3,
};

export function References({ references }: ReferencesProps) {
  if (!references || !references.length) {
    return <p className="report-muted-empty">No references available.</p>;
  }

  return (
    <div className="report-reference-table-wrap">
      <table className="report-reference-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Type</th>
            <th>Description</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {references.filter(Boolean).map((reference, index) => {
            const type = formatText(reference.type || 'reference');
            const Icon = TYPE_ICONS[type] || Database;

            return (
              <tr key={formatText(reference.id || index)}>
                <td className="id">[{formatText(reference.id || index + 1)}]</td>
                <td>
                  <span className="report-reference-type">
                    <Icon size={11} />
                    {type}
                  </span>
                </td>
                <td>{formatText(reference.description, '-')}</td>
                <td className="source">{formatText(reference.source, '-')}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
