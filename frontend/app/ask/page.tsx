import { permanentRedirect } from 'next/navigation';

// Ask Genesis is now part of the unified Workbench. Keep the legacy URL working for old
// bookmarks and cached PWA shortcuts without mounting a second chat application.
export default function LegacyAskPage() {
  permanentRedirect('/workbench');
}
