import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layouts/AppShell";
import { ChangeListsPage } from "./pages/ChangeListsPage";
import { DraftsPage } from "./pages/DraftsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { QaPage } from "./pages/QaPage";
import { QueuePage } from "./pages/QueuePage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/queue" replace />} />
          <Route path="queue" element={<QueuePage />} />
          <Route path="drafts" element={<DraftsPage />} />
          <Route path="qa" element={<QaPage />} />
          <Route path="change-lists" element={<ChangeListsPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/queue" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
