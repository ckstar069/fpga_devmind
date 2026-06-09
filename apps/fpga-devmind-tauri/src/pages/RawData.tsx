import type { ProjectBundle } from "../types";

interface Props {
  bundle: ProjectBundle;
}

function RawData({ bundle }: Props) {
  return (
    <div>
      <div className="page-title">Raw Data</div>
      <div className="page-subtitle">
        完整 project_understanding_graph.json
      </div>
      <div className="raw-json">
        {JSON.stringify(bundle.graph, null, 2)}
      </div>
    </div>
  );
}

export default RawData;
