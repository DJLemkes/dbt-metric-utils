# dbt-metric-utils

This tool allows you to query metrics from your dbt semantic model directly from a dbt model through the `dbt_metric_utils_materialize` macro. One way to look at it is that it revives the `metric.calculate()` macro from dbt `<=v1.5`. By having access to this macro, the dbt semantic layer becomes more useful for dbt-core users. You still don't have all the goodness of dbt-cloud semantic layer but it does allow you to get started with connecting your users and BI tools to aggregation tables/views that are directly querying your metrics.

> [!TIP]
> Check out some examples queries [here](./jaffle-shop/models/marts/materialized_metrics/)

> [!TIP]
> Browse the dbt docs pages for the example project [here](https://djlemkes.github.io/dbt-metric-utils)

## Installation instructions

This project is a Python package that wraps around `dbt` in the most transparant way I could find. Try it out through the following steps:

1. Install `dbt-metric-utils` from Pypi in your project (e.g. `pip install dbt-metric-utils`)
1. Run `dbt-metric-utils init` or `dbtmu init`. This will install the macro into your project and will make sure that any `dbt` CLI calls are intercepted and processed in the correct way (check below for explanation)
1. Introduce a dbt model that calls the `dbt_metric_utils_materialize` macro.
1. Continue using `dbt` as you're used to.

## How it works

Any dbt command that doesn't require dbt to compile your project is simply passed directly to dbt (Mode A in the diagram). A dbt invocation that does require compilation (e.g. `compile`, `run`, `test` , etc) is intercepted by the package.

![](assets/how_it_works.png)

After intercepting we run through the following sequence of steps

1. Call `dbt parse` . This will build a partially filled `manifest.json` from which we can extract all the models, their dependencies, and the raw SQL queries.
2. Extract all models that contain a `dbt_metric_utils_materialize` invocation.
3. Run `mf query --explain` commands for all the `dbt_metric_utils_materialize` invocations.
4. Inject the generated queries by Metricflow as dbt variables in the actual dbt command. If the user ran `dbt run` , we actually trigger `dbt run --vars {<macro_invocation_signature>: <query>}` 

The passed variables will be a mapping from `dbt_metric_utils_materialize` invocation signature (e.g. `metric=['m1'],dimensions='[dim1']...` ) to the generated metric query. The  `dbt_metric_utils_materialize` macro will find that variable at compile time and return it as the macro result. 

Along this sequence of steps, we also ensure that the dependency graph in `manifest.json` is updated correctly. Dbt itself only detects dependencies based on `ref` and `source` , not on macros that are external to it.
