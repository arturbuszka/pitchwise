import { api } from "@/lib/api";
import { HomeClient } from "@/components/HomeClient";

export default async function Home() {
  const matches = await api.matches.list().catch(() => []);
  return <HomeClient matches={matches} />;
}
