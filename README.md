# Parkrun Analyser
Analyse Parkrun results by scrapping an athlete's Parkrun page to generate data on their results.

## How to run

The script has one required argument - the ID of the athlete you wish to analyse.

```python parkrun_analyser --athlete_id <athlete ID>```

To get a map of the Parkrun's that athlete has attended add the `--map` flag.

```python parkrun_analyser --athlete_id <athlete ID> --map```
