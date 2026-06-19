import { api } from "@/lib/api";
import { UploadForm } from "@/components/UploadForm";
import Link from "next/link";

export default async function Home() {
  const matches = await api.matches.list().catch(() => []);

  return (
    <div className="max-w-4xl mx-auto w-full px-6 py-10 flex flex-col gap-8">
      <section>
        <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-widest mb-4">
          Nowy mecz
        </h2>
        <UploadForm />
      </section>

      <section>
        <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-widest mb-4">
          Mecze ({matches.length})
        </h2>
        {matches.length === 0 ? (
          <p className="text-gray-500 text-sm">Brak meczów. Wgraj nagranie powyżej.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {matches.map((m) => (
              <li key={m.id}>
                <Link
                  href={`/matches/${m.id}`}
                  className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 hover:border-gray-600 transition-colors"
                >
                  <div>
                    <p className="font-medium text-white">{m.title}</p>
                    <p className="text-gray-500 text-sm mt-0.5">
                      {new Date(m.created_at).toLocaleString("pl-PL")}
                      {m.duration_seconds
                        ? ` · ${Math.round(m.duration_seconds / 60)} min`
                        : ""}
                    </p>
                  </div>
                  <span className="text-gray-600 text-sm">→</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
