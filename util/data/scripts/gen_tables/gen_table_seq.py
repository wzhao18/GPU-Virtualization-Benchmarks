import data.scripts.common.constants as const
import data.scripts.common.help_iso as hi

import argparse
import os
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser('Generate dataframe pickle '
                                     'for sequential run from csv.')
    parser.add_argument('--csv',
                        default=os.path.join(const.DATA_HOME, 'csv/seq.csv'),
                        help='CSV file to parse')
    parser.add_argument('--output',
                        default=os.path.join(const.DATA_HOME,
                                             'pickles/seq.pkl'),
                        help='Output path for the dataframe pickle')

    results = parser.parse_args()
    return results


# Parse arguments
args = parse_args()

# Read CSV file
df = pd.read_csv(args.csv)

hi.multi_array_col_seq(df)

# calculate ipc for multi seq
df['ipc'] = df['instructions'] / df['runtime']

# drop any benchmarks that have zero runtime
df = df[df['runtime'] > 0]

# avg dram bandwidth
df['avg_dram_bw'] = df['dram_bw'].transform(hi.avg_array)
df['avg_dram_eff'] = df['dram_eff'].transform(hi.avg_array)
df['avg_row_locality'] = df['row_buffer_locality'].transform(hi.avg_array)

# standard deviation of dram bandwidth among channels
df['std_dram_bw'] = df['dram_bw'].transform(hi.std_array)
df['ratio_dram_bw'] = df['std_dram_bw'] / df['avg_dram_bw']

# MPKI
df['MPKI'] = df['l2_total_accesses'] * df['l2_miss_rate'] \
             / (df['instructions'] / 1000)

# l2_accesses
df['l2_access_density'] = df['l2_total_accesses'] / (df['instructions'] / 1000)

# parse config for multi-kernel benchmarks
hi.process_config_column('1_kidx', df=df, default=1)


def calc_waves(row):
    max_cta = const.get_max_cta_per_sm(row['pair_str'], row['1_kidx'])
    grid_size = const.get_grid_size(row['pair_str'], row['1_kidx'])

    return grid_size / max_cta / const.num_sm_volta


df['waves'] = df.apply(calc_waves, axis=1)

# PATCH for GPGPU-Sim not_selected_cycles
df['not_selected_cycles'] = df['cycles_per_issue'] - \
                            df['stall_mem_cycles'] - \
                            df['stall_sfu_cycles'] - \
                            df['stall_tensor_cycles'] - \
                            df['stall_int_cycles'] - \
                            df['stall_dp_cycles'] - \
                            df['stall_sp_cycles'] - \
                            df['scoreboard_cycles'] - \
                            df['branch_cycles'] - \
                            df['inst_empty_cycles'] - \
                            df['barrier_cycles']

# sort table based on benchmark name and kidx
df.sort_values(['pair_str', '1_kidx'], inplace=True)

# Output pickle
df.to_pickle(args.output)
