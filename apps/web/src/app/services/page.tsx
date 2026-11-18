import { ServiceWorkspace } from "../../features/documents/ServiceWorkspace";
import { OperationalServiceWorkspace } from "../../features/documents/OperationalServiceWorkspace";
export default function ServicesPage() { return process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" ? <OperationalServiceWorkspace /> : <ServiceWorkspace />; }
