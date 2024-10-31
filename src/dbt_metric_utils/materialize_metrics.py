import re
from datetime import datetime
from typing import Dict, List, Tuple

import yaml
from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt_metricflow.cli.cli_context import CLIContext
from metricflow.engine.metricflow_engine import MetricFlowQueryRequest

mf = None
new_dbt_vars: Dict[str, str] = {}
materialized_metric_dependencies = {}


def dbt_metric_utils_materialize(
    node_id: str,
    metrics: List[str],
    dimensions: List[str] | None = None,
    group_by: List[str] | None = None,
    limit: int | None = None,
    time_start: str | None = None,
    time_end: str | None = None,
    where: str | None = None,
    order_by: List[str] | None = None,
):
    """
    This function should have _exactly_ the same name as our macro in dbt_metric_utils_materialize.sql
    because it will be called via exec(). Yes, this is dirty, and it works :D.
    """
    global new_dbt_vars
    global materialized_metric_dependencies
    global mf

    mf_request = MetricFlowQueryRequest.create_with_random_request_id(
        metric_names=metrics,
        group_by_names=group_by,
        limit=limit,
        time_constraint_start=datetime.strptime(time_start, "%Y-%m-%d") if time_start else None,
        time_constraint_end=datetime.strptime(time_end, "%Y-%m-%d") if time_end else None,
        where_constraint=where,
        order_by_names=order_by,
    )

    mf_query = mf.explain(mf_request).rendered_sql_without_descriptions.sql_query

    # Python renders no value as 'None' and Jinja as empty string.
    new_dbt_vars[
        f"metrics={metrics},dimensions={dimensions or ''},group_by={group_by or ''},"
        + f"limit={limit or ''},time_start={time_start or ''},"
        + f"time_end={time_end or ''},where={where or ''},order_by={order_by or ''}"
    ] = mf_query
    materialized_metric_dependencies[node_id] = metrics


def _write_metric_queries(dbt_target: str | None = None) -> dict:
    global mf
    dbt = dbtRunner()
    res: dbtRunnerResult = dbt.invoke(
        ["parse", "--quiet"]
        if dbt_target is None
        else ["parse", "--target", dbt_target, "--quiet"]
    )
    manifest = res.result
    mf = CLIContext().mf

    materialize_calls_raw_sql = [
        (n.unique_id, n.raw_code) for k, n in manifest.nodes.items() if "model." in k
    ]
    materialize_calls = [
        (x[0], m.group(0))
        for x in materialize_calls_raw_sql
        if (m := re.search(r"dbt_metric_utils_materialize\(.*\)", x[1], re.DOTALL))
    ]

    for node_id, mc in materialize_calls:
        # LOL so dirty :D.
        # We need to inject the node_id to the function call so that we can fix the dependency graph below.
        mc_split = mc.split("(")
        mc_with_node_id = "".join([mc_split[0], f"('{node_id}', ", *mc_split[1:]])
        exec(mc_with_node_id)

    metric_name_to_fqn = {m.name: m.unique_id for m in manifest.metrics.values()}

    # Fix dependency graph so that dbt knows which queries to run first
    for node_id, metrics in materialized_metric_dependencies.items():
        metric_fqns = [metric_name_to_fqn[m] for m in metrics]
        manifest.nodes[node_id].depends_on.nodes.extend(metric_fqns)

    return manifest


def get_metric_queries_as_dbt_vars(dbt_target: str | None = None) -> Tuple[dict, str]:
    manifest = _write_metric_queries(dbt_target)
    return manifest, yaml.dump(new_dbt_vars, default_flow_style=False)
