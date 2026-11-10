import * as React from "react";
import { getCurrentItem, onItemChanged, type CurrentItem } from "../../office/mailbox";

/** The selected email; updates when a pinned pane follows the selection. */
export function useCurrentItem(): CurrentItem | null {
  const [item, setItem] = React.useState<CurrentItem | null>(() => getCurrentItem());
  React.useEffect(() => onItemChanged(() => setItem(getCurrentItem())), []);
  return item;
}
