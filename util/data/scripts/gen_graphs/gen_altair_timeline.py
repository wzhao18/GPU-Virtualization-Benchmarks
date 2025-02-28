import altair as alt
import pandas as pd
import numpy as np
import os
import re
from itertools import cycle

import data.scripts.common.constants as const
import data.scripts.common.help_iso as hi


def _prepare_data_from_timestamps(timestamps, norm_ipc, apps):
    def get_kernels(stream_id, length):
        kernels = np.arange(1, const.get_num_kernels(apps[stream_id-1]) + 1)
        kernels = np.resize(kernels, length)
        kernels = ['{}:{}'.format(stream_id, k) for k in kernels]

        return kernels

    s1 = np.repeat('1: ' + apps[0], timestamps[0][0].shape[0])
    k1 = get_kernels(1, timestamps[0][0].shape[0])

    s2 = np.repeat('2: ' + apps[1], timestamps[1][0].shape[0])
    k2 = get_kernels(2, timestamps[1][0].shape[0])

    col_from = np.concatenate(timestamps[:, 0])
    col_to = np.concatenate(timestamps[:, 1])
    col_stream = np.concatenate((s1, s2))
    col_kernel = np.concatenate((k1, k2))
    col_norm = np.concatenate(norm_ipc)

    data = pd.DataFrame()
    data["start"] = col_from
    data["end"] = col_to
    data["stream"] = col_stream
    data["kernel"] = col_kernel
    data['position'] = (data['start'] + data['end']) / 2
    data['norm'] = col_norm
    data['norm'] = data['norm'].round(2)

    return data


def _prepare_gpusim_metrics(pair_series):
    runtime = pair_series['runtime']
    s1_runtime = runtime[-2]
    s2_runtime = runtime[-1]

    norm_runtime = pair_series['norm_ipc']
    s1_norm = norm_runtime[-2]
    s2_norm = norm_runtime[-1]


    s1_from, s1_to = const.get_from_to(s1_runtime)
    s2_from, s2_to = const.get_from_to(s2_runtime)

    timestamps = [[s1_from, s1_to], [s2_from, s2_to]]
    apps = [pair_series['1_bench'], pair_series['2_bench']]
    norm_ipc = [s1_norm, s2_norm]

    data = _prepare_data_from_timestamps(timestamps, apps, norm_ipc)

    return data


def prepare_gpusim_console(pair_str, filename, config_str):
    # Assuming the timeline file is in
    # util/data/timeline/pair_str/filename
    timeline_file = os.path.join(const.DATA_HOME,
                                 'timeline/{}/{}'.format(pair_str,
                                                         filename))

    apps = re.split(r'-(?=\D)', pair_str)
    seq_cycles = [const.get_seq_cycles(app) for app in apps]
    circular_seq_cycles = [cycle(c) for c in seq_cycles]

    # Prepare dataframe for Altair
    data = []
    with open(timeline_file) as f:
        for line in f:
            stream_id = int(re.search(r"Stream\s(.*)\skernel", line).group(1))
            kernel = re.search(r"kernel\s(.*)\slaunched", line).group(1)
            start = int(re.search(r"started\s@\s(.*),", line).group(1))
            end = int(re.search(r"ended\s@\s(.*)\.", line).group(1))
            position = (start + end) / 2
            runtime = end - start

            isolated_duration = next(circular_seq_cycles[stream_id - 1])
            norm = (isolated_duration / runtime).round(2)

            entry = {'stream': "{}: {}".format(stream_id, apps[stream_id - 1]),
                     'kernel': kernel,
                     'start': start,
                     'end': end,
                     'norm': norm,
                     'runtime': runtime,
                     'position': position,
                     }
            data.append(entry)

    data = pd.DataFrame(data)

    # Check if simulation hit max_cycles
    config_cap = hi.check_config('cap', config_str, default=0)
    if config_cap == data['end'].max():
        print("{}, {} simulation hit max cycles ({}).".format(pair_str,
                                                              config_str,
                                                              config_cap))

        # Get rid of the final incomplete kernel
        adjusted_data = data[data['end'] != config_cap]
    else:
        adjusted_data = data

    # Make sure we get at least one iteration in each app
    stream_tokens = sorted(adjusted_data['stream'].unique())
    shared_runtime = [adjusted_data[adjusted_data['stream'] == token]
                      ['runtime'] for token in stream_tokens]

    at_least_one_iter = [(len(shared) >= len(isolated))
                         for shared, isolated in zip(shared_runtime, seq_cycles)
                         ]

    if all(at_least_one_iter):
        # calculate_sld_short needs the original copy of shared_runtime
        # shared runtime is also iteration based
        shared_end_stamp = [data[data['stream'] == token].sort_values('start')
                            ['end'] for token in stream_tokens]

        sld = hi.calculate_sld_short(shared_end_stamp, seq_cycles)

        return data, sld
    else:
        print("{}, {} did not finish at least one iteration. Skip.".format(
            pair_str, config_str))
        return pd.DataFrame(), 0


def draw_altair(data, chart_title, width=900, xmax=None):
    xmax = xmax if xmax else data['end'].max()

    bars = alt.Chart(data, title=chart_title).mark_bar().encode(
        x=alt.X("start", title='Cycles', scale=alt.Scale(domain=(0, xmax))),
        x2="end",
        y=alt.Y("stream", sort=None),
        color=alt.Color('kernel', scale=alt.Scale(scheme='pastel1'),
                        legend=None)
    ).properties(
        width=width,
        height=100
    )

    text = alt.Chart(data).mark_text(
        align='center',
        baseline='middle',
        color='black',
        fontSize=12,
        angle=90,
    ).encode(
        y=alt.Y('stream', title=None, sort="ascending"),
        x='position',
        text='norm'
    )

    return alt.layer(bars, text).configure_axis(
        grid=False
    ).configure_header(
        titleColor='black',
        titleFontSize=14,
    )


# Assume kernels are launched back to back
# Required fields in pair_series: 1_bench, 2_bench, runtime, norm_ipc
def draw_timeline_from_metrics(pair_series, col_title=None, title=None):
    # 1. Prepare data
    data = _prepare_gpusim_metrics(pair_series)

    if col_title:
        chart_title = "{0} = {1}".format(col_title, pair_series[col_title])
    elif title:
        chart_title = "{0}".format(title)
    else:
        chart_title = ""

    # 2. Draw altair objects
    return draw_altair(data, chart_title)


def draw_timeline_from_console(pair_str, filename, title=None,
                               width=900, xmax=None):
    config_str = os.path.basename(filename).replace('.txt', '')
    data, sld = prepare_gpusim_console(pair_str, filename, config_str)

    if data.empty:
        return None

    if not title:
        if hi.check_config('lut', config_str, default=False):
            title = "LUT (3D Allocation)"
        else:
            ctx_1 = hi.check_config('1_ctx', config_str, default=0)
            ctx_2 = hi.check_config('2_ctx', config_str, default=0)
            title = "CTX-{}-{}".format(ctx_1, ctx_2)

    return draw_altair(data, title, width, xmax), sld


def draw_timeline_from_prediction(timestamps, apps, norm_ipc,
                                  title, width=900, xmax=None):

    data = _prepare_data_from_timestamps(timestamps=timestamps,
                                         norm_ipc=norm_ipc,
                                         apps=apps)

    return draw_altair(data, title, width, xmax)

