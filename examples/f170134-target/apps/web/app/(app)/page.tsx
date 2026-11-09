import { SuccessMessage, ErrorRegion } from '../../components/Alerts';
import { BarChart, PieChart } from '../../components/Charts';
import { PageHeader } from '../../components/PageHeader';
import { apiGet } from '../../lib/api';
import { apiErrorOnly } from '../../lib/guard';
import { first, type SearchParams } from '../../lib/routes';
import { page } from '../../lib/spec';

interface Home {
  kpis: { seq: string; icon: string; label: string; metric_value: string }[];
  byStatus: { label: string; value: string }[];
  byDepartment: { label: string; value: string }[];
}

/** Page 100 Home: static region, metric cards "Ringkasan" (apx_demo_dash_kpi_v) and two JET charts. */
export default async function HomePage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const sp = await searchParams;
  const p = page(100);
  let data: Home;
  try {
    data = await apiGet<Home>('/pages/100');
  } catch (e) {
    return <ErrorRegion error={apiErrorOnly(e)} />;
  }
  return (
    <>
      <PageHeader page={100} title={p.title} />
      <SuccessMessage flash={first(sp.msg)} />
      <div className="region"><p style={{ margin: 0 }}>{p.region.Home.plugSource}</p></div>
      <section className="region" aria-labelledby="r-ringkasan">
        <h2 id="r-ringkasan">Ringkasan</h2>
        <div className="metrics" data-testid="kpis">
          {data.kpis.map((k) => (
            <div className="metric" key={k.seq} data-icon={k.icon}>
              <div className="icon" aria-hidden="true">●</div>
              <div><div className="value">{k.metric_value}</div><div className="label">{k.label}</div></div>
            </div>
          ))}
        </div>
      </section>
      <div className="grid-2">
        <section className="region" aria-labelledby="r-status">
          <h2 id="r-status">Permintaan per Status</h2>
          <PieChart data={data.byStatus} title="Permintaan per Status" />
        </section>
        <section className="region" aria-labelledby="r-dept">
          <h2 id="r-dept">Nilai per Department</h2>
          <BarChart data={data.byDepartment} title="Nilai per Department" />
        </section>
      </div>
    </>
  );
}
