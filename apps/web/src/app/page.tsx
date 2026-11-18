import HomeOverview from "../features/home/HomeOverview";

export default async function HomePage({ searchParams }: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  return <HomeOverview searchParams={await searchParams} />;
}
