import { ReactNode } from 'react';

import { InfoTooltip } from './InfoTooltip';

type WorkspacePageHeaderProps = {
  title: string;
  description: string;
  actions?: ReactNode;
};

export function WorkspacePageHeader({ title, description, actions }: WorkspacePageHeaderProps) {
  return (
    <>
      <div className="section-title tab-header">
        <div>
          <div className="section-title-row">
            <h2>{title}</h2>
            <InfoTooltip text={description} />
          </div>
        </div>
        {actions ? <div className="header-actions">{actions}</div> : null}
      </div>
      <div className="section-divider" />
    </>
  );
}
