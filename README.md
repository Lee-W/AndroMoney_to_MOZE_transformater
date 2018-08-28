# AndroMoney to MOZE transformater
Tool for porting accounting data from AndroMoney to MOZE

## Pre-requsite
```sh
pipenv install .
```

## Usage
```sh
python transformater.py [OPTIONS] COMMAND [ARGS]...
```

- Options
	- `--input_file TEXT` Input Filename (default: AndroMoney - AndroMoney.csv)
	- `--output_file TEXT` Output Filename (default: MOZE.csv)
	- `--help` Show this message and exit.

- Commands
	- `extract` Extarct the information that need to be manual created in MOZE
	- `transformat` Transformat Andromoney export file to MOZE import file  

### Example
```sh
python transformater.py transformat --input_file AndroMoney.csv --output_file MOZE.csv
```

## Authors
[Lee-W](https://github.com/Lee-W)

## License
MIT