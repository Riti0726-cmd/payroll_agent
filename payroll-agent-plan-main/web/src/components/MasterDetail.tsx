import type { ReactNode } from "react";
import styles from "./MasterDetail.module.css";

type MasterDetailProps = {
  list: ReactNode;
  detail: ReactNode;
  listLabel: string;
};

export function MasterDetail({ list, detail, listLabel }: MasterDetailProps) {
  return (
    <section className={styles.shell} data-enter>
      <div aria-label={listLabel} className={styles.listPane} role="region">
        <div className={styles.listLabel}>{listLabel}</div>
        <div className={styles.listBody}>{list}</div>
      </div>
      <div aria-label="Detail" className={styles.detailPane} role="region">
        {detail}
      </div>
    </section>
  );
}
