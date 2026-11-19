import { KnowledgePlatform } from "../../../features/knowledge/KnowledgePlatform";
export default function SourcesPage() { return process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" ? null : <KnowledgePlatform />; }
