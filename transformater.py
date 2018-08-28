from copy import deepcopy
from datetime import datetime

import click
import numpy as np
import pandas as pd


pd.options.mode.chained_assignment = None

DEFAULT_ANDROMONEY_FILENAME = 'AndroMoney - AndroMoney.csv'
DEFAULT_MOZE_FILENAME = 'MOZE.csv'

MOZE_HEADER = [
    # Required
    '帳戶',
    '幣別',
    # Required
    '記錄類型', '主類別', '子類別', '金額',
    '手續費', '名稱', '商家', '交易方式',
    # Required
    '日期',
    '時間', '專案', '描述', '標籤', '相關行數'
]

ANDROMONEY_TO_MOZE_COL_MAPPING = {
    'Currency': '幣別',
    'Category': '主類別',
    'Sub-Category': '子類別',
    'Payee/Payer': '商家',
    'Remark': '描述',
    # 'Project': '專案',
    'Amount': '金額',  # +/-
    'Date': '日期',    # format
    'Time': '時間',    # foramt
    # --- for future use ---
    'Expense(Transfer Out)': 'Expense',
    'Income(Transfer In)': 'Income',
}


def load_andromoney_records(filename=DEFAULT_ANDROMONEY_FILENAME):
    df = pd.read_csv(filename, skiprows=1)
    df['is_income'] = (
        df['Expense(Transfer Out)'].isna() & df['Income(Transfer In)'].notna()
    )
    df['is_expense'] = (
        df['Income(Transfer In)'].isna() & df['Expense(Transfer Out)'].notna()
    )
    df['is_transfer'] = (
        df['Expense(Transfer Out)'].notna() & df['Income(Transfer In)'].notna()
    )
    return df


def extract_manual_input_for_moze(andro_df):
    # Extract all accounts
    accounts = (
        (
            set(andro_df['Expense(Transfer Out)']) |
            set(andro_df['Income(Transfer In)'])
        ) -
        {np.nan}
    )

    # Extract default account amount
    system_df = andro_df[andro_df.Category == 'SYSTEM'][['Income(Transfer In)', 'Amount']]
    system_df.sort_values(by=['Amount'], inplace=True, ascending=False)
    system_df.reset_index(inplace=True)
    system_df.drop(columns='index', inplace=True)
    system_df.columns = ['Account', 'Amount']

    # Extract all projects
    projects = set(andro_df.Project) - {np.nan}

    # Extract categories and sub-categories
    categoires = set(andro_df.Category)
    categoires_dict = {
        category: set()
        for category in categoires
    }
    for category, sub_category in zip(andro_df.Category, andro_df['Sub-Category']):
        categoires_dict[category].add(sub_category)
    return accounts, system_df, projects, categoires_dict


def transformat_andromoney_to_moze(andro_df):
    # Drop system initial
    andro_df = andro_df[andro_df.Category != 'SYSTEM']

    # Map andro_df to moze_df
    moze_df = pd.DataFrame(columns=MOZE_HEADER)
    for andro_col, moze_col in ANDROMONEY_TO_MOZE_COL_MAPPING.items():
        moze_df[moze_col] = andro_df[andro_col]

    # Set 記錄類型
    andro_df.loc[andro_df.is_expense == True, '記錄類型'] = '支出'
    andro_df.loc[andro_df.is_income == True, '記錄類型'] = '收入'
    andro_df.loc[andro_df.is_transfer == True, '記錄類型'] = '轉帳'
    moze_df['記錄類型'] = andro_df['記錄類型']

    # Update plus/minus of amount
    moze_df.loc[moze_df.記錄類型 == '支出', '金額'] = (
        -moze_df.loc[moze_df.記錄類型 == '支出', '金額']
    )

    # Update date/time format
    moze_df.日期 = moze_df.日期.apply(
        lambda x: datetime.strptime(str(x), '%Y%m%d').strftime('%Y/%m/%d')
    )
    moze_df.loc[moze_df.時間.notna(), '時間'] = moze_df.時間[moze_df.時間.notna()].apply(
        lambda x: datetime.strptime('{0:04d}'.format(int(x)), '%H%M').strftime('%H:%M')
    )

    # Set up amount for none transfer records
    moze_non_transfer_df = moze_df[moze_df.記錄類型 != '轉帳']
    moze_non_transfer_df = moze_df[moze_df.記錄類型 != '轉帳']
    moze_non_transfer_df.loc[moze_non_transfer_df.Expense.notna(), '帳戶'] = (
        moze_non_transfer_df.loc[moze_non_transfer_df.Expense.notna(), 'Expense']
    )
    moze_non_transfer_df.loc[moze_non_transfer_df.Income.notna(), '帳戶'] = (
        moze_non_transfer_df.Income[moze_non_transfer_df.Income.notna()]
    )

    # Split transfer records into in and our
    moze_transfer_out_df = moze_df[moze_df.記錄類型 == '轉帳']
    moze_transfer_out_df.主類別 = '轉出'
    moze_transfer_out_df.reset_index(inplace=True)
    moze_transfer_out_df['transfer_pesudo_id'] = moze_transfer_out_df.index.values
    moze_transfer_out_df.drop(columns=['index'], inplace=True)
    moze_transfer_in_df = deepcopy(moze_transfer_out_df)
    moze_transfer_in_df.主類別 = '轉入'

    # Set up amount for transfer records
    moze_transfer_out_df.帳戶 = moze_transfer_out_df.Expense
    moze_transfer_in_df.帳戶 = moze_transfer_in_df.Income

    # Set up minus account for transfer out records
    moze_transfer_out_df.金額 = -moze_transfer_out_df.金額

    # Merge transfer in, out records
    transfer_header = moze_transfer_out_df.columns
    transfer_data = list()
    for r_out, r_in in zip(moze_transfer_out_df.values, moze_transfer_in_df.values):
        transfer_data.append(r_out)
        transfer_data.append(r_in)

    moze_transfer_df = pd.DataFrame(transfer_data, columns=transfer_header)

    moze_df = moze_transfer_df.append(moze_non_transfer_df, sort=False)
    moze_df.sort_values(by=['日期', '時間', '記錄類型'], inplace=True)
    moze_df.reset_index(inplace=True)

    cur_id, cur_index = -1, -1
    row_indexs = list()
    first_row_indexes = list()
    for row_index, row in enumerate(moze_df.values):
        if not np.isnan(row[-1]):
            if row[-1] != cur_id:
                cur_id = row[-1]
                cur_index = row_index
            row_indexs.append(row_index)
            first_row_indexes.append(cur_index+2)
    moze_df.相關行數.iloc[row_indexs] = first_row_indexes
    moze_df = moze_df[MOZE_HEADER]
    return moze_df


@click.group()
@click.option('--input_file', default=DEFAULT_ANDROMONEY_FILENAME,
              help=f'Input Filename (default: {DEFAULT_ANDROMONEY_FILENAME})')
@click.option('--output_file', default=DEFAULT_MOZE_FILENAME,
              help=f'Output Filename (default: {DEFAULT_MOZE_FILENAME})')
@click.pass_context
def main(ctx, input_file, output_file):
    ctx.obj['input_file'] = input_file
    ctx.obj['output_file'] = output_file


@main.command()
@click.pass_context
def transformat(ctx):
    """Transformat Andromoney export file to MOZE import file"""
    input_file = ctx.obj['input_file']
    output_file = ctx.obj['output_file']

    andro_df = load_andromoney_records(input_file)
    moze_df = transformat_andromoney_to_moze(andro_df)
    moze_df.to_csv(output_file, index=False)


@main.command()
@click.pass_context
def extract(ctx):
    """Extarct the information that need to be manual created in MOZE"""
    input_file = ctx.obj['input_file']

    andro_df = load_andromoney_records(input_file)
    accounts, inital_df, projects, categoires_dict = extract_manual_input_for_moze(andro_df)

    click.secho('Accounts (Intial Amount)', fg='red', underline=True)
    for account in accounts:
        inital_amount = inital_df.loc[inital_df.Account == account, 'Amount'].values
        if inital_amount.size:
            inital_amount = float(inital_amount[0])
        click.echo(f'{account}: {inital_amount}')

    click.secho('\nProject', fg='red', underline=True)
    for project in projects:
        click.echo(f'{project}')

    click.secho('\nCategory', fg='red', underline=True)
    for category, sub_categories in categoires_dict.items():
        click.echo(f'{category}')
        for sub_category in sub_categories:
            click.echo(f'\t{sub_category}')


if __name__ == "__main__":
    main(obj={})
