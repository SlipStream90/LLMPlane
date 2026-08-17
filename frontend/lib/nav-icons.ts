import {
  LayoutDashboard,
  Network,
  Server,
  Container,
  GitBranch,
  Play,
  FileText,
  FlaskConical,
  Trophy,
  CheckCircle,
  Medal,
  Eye,
  ScrollText,
  DollarSign,
} from "lucide-react";

/**
 * Nav-icon lookup, in one place.
 *
 * This 14-entry map was previously duplicated verbatim in both `Sidebar.tsx`
 * and `CommandPalette.tsx`, so adding a nav item meant editing two files and
 * forgetting one made the icon silently vanish from the palette.
 */
export const NAV_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  Network,
  Server,
  Container,
  GitBranch,
  Play,
  FileText,
  FlaskConical,
  Trophy,
  CheckCircle,
  Medal,
  Eye,
  ScrollText,
  DollarSign,
};
