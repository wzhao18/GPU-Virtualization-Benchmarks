import sys
import numpy as np
import argparse
import os
from collections import defaultdict
from scipy import stats
import copy
from gpupool.core.workload import BatchJob, GpuPoolConfig, Job
from gpupool.core.predict import Allocation, StageOne, StageTwo


def parse_args():
    parser = argparse.ArgumentParser("Get main paper results from pickle.")

    parser.add_argument('--pkl', nargs='+',
                        help='Path to pickle file')
    parser.add_argument('--job_count', type=int, default=100,
            help='Number of jobs in the batch')
    parser.add_argument('--stage2_buffer', nargs='+',
                        type=float,
                        help='Amount of buffer to tighten qos check in stage2.')

    results = parser.parse_args()

    if len(results.pkl) != len(results.stage2_buffer):
        print("Length of pkl must match with stage2_buffer")
        sys.exit(1)

    return results


def main():
    args = parse_args()

    ids = []
    batches = []
    count = defaultdict(list)
    ws = defaultdict(list)
    ws_list = defaultdict(list)
    violation = defaultdict(list)

    for pkl, stage2 in zip(args.pkl, args.stage2_buffer):
        pkl_name = str(os.path.basename(pkl).split('.')[0])
        params = pkl_name.split('-')
        batch_id = int(params[1])
        ids.append(batch_id)

        Job.count = args.job_count * batch_id 
        batch = BatchJob(rand_seed=batch_id, num_jobs=args.job_count)
        batch.load_df_from_pickle(pkl)

        # GPUPool
        config = GpuPoolConfig(Allocation[params[2]], StageOne[params[3]],
                               StageTwo[params[4]],
                               at_least_once=(params[5] == "True"),
                               accuracy_mode=False,
                               stage2_buffer=stage2)

        gpupool_matching = batch.max_matching(config, cores=32)
        gp_count, gp_violation, gp_ws, gp_ws_list, isolated = gpupool_matching

        print("GPUPool GPU count:", gp_count)
        print("WS:", gp_ws)
        print(gp_violation.to_string(args.job_count))

        if gp_violation.count > 0:
            print("Non-zero violations.")
            sys.exit(1)

        count['gpupool'].append(gp_count)
        ws['gpupool'].append(gp_ws)
        ws_list['gpupool'].append(copy.deepcopy(gp_ws_list))
        violation['gpupool'].append(copy.deepcopy(gp_violation))

        # MIG
        mig_count, mig_ws, mig_ws_list = batch.calculate_gpu_count_mig()
        print("MIG count:", mig_count)
        print("MIG WS", mig_ws)

        count['mig'].append(mig_count)
        ws['mig'].append(mig_ws)
        ws_list['mig'].append(copy.deepcopy(mig_ws_list))

        # Heuristic
        heuristic_count = args.job_count / 2
        bw_violation, bw_ws_list, bw_gpu_total = \
            batch.calculate_qos_viol_dram_bw(heuristic_count,
                                             cores=32)
        bw_ws = sum(bw_ws_list) / bw_gpu_total

        print("Heuristic count", bw_gpu_total)
        print("Heuristic WS", bw_ws)

        count['bw'].append(bw_gpu_total)
        ws['bw'].append(bw_ws)
        ws_list['bw'].append(copy.deepcopy(bw_ws_list))
        violation['bw'].append(copy.deepcopy(bw_violation))
        # similarity
        sim_violation, sim_ws_list, sim_gpu_total = \
            batch.calculate_qos_viol_similarity(cores=32)
        sim_ws = sum(sim_ws_list) / sim_gpu_total

        print("Similarity count", sim_gpu_total)
        print("Similarity WS", sim_ws)
        print("Similarity violation", sim_violation.to_string(
            num_jobs=args.job_count))

        batches.append(copy.deepcopy(batch))

    if len(args.pkl) == 1:
        print("Single pickle. No output files.")
        return

    ##############################################
    # CSV file output 1: main result
    ##############################################
    comparison_csv = open('main_result.csv', 'w')
    comparison_csv.write('system,gpus,sem_gpus,sd_gpus,stp,sem_stp,sd_stp\n')
    comparison_csv.write('coarse,{},{},{},{},{},{}\n'.format(
        np.average(count['mig']),
        stats.sem(count['mig']),
        np.std(count['mig']),
        np.average(ws['mig']),
        stats.sem(ws['mig']),
        np.std(ws['mig'])))
    comparison_csv.write('bw,{},{},{},{},{},{}\n'.format(
        np.average(count['bw']),
        stats.sem(count['bw']),
        np.std(count['bw']),
        np.average(ws['bw']),
        stats.sem(ws['bw']),
        np.std(ws['bw'])))
    comparison_csv.write('gpupool,{},{},{},{},{},{}\n'.format(
        np.average(count['gpupool']),
        stats.sem(count['gpupool']),
        np.std(count['gpupool']),
        np.average(ws['gpupool']),
        stats.sem(ws['gpupool']),
        np.std(ws['gpupool'])))
    comparison_csv.close()

    comparison_tbl = open("main_result.tex", 'w')
    comparison_tbl.write(
        "\\coarse &      {} $\\pm$ {:.2f} &       {:.2f} $\\pm$ {}\n".format(
            np.average(count['mig']),
            stats.sem(count['mig']),
            np.average(ws['mig']),
            stats.sem(ws['mig'])))
    comparison_tbl.write(
        "\\heuristic &      {} $\\pm$ {:.2f} &       {:.2f} $\\pm$ {}\n".format(
            np.average(count['bw']),
            stats.sem(count['bw']),
            np.average(ws['bw']),
            stats.sem(ws['bw'])))
    comparison_tbl.write(
        "\\gpupool &      {} $\\pm$ {:.3f} &       {:.2f} $\\pm$ {}\n".format(
            np.average(count['gpupool']),
            stats.sem(count['gpupool']),
            np.average(ws['gpupool']),
            stats.sem(ws['gpupool'])))

    ##############################################
    # CSV file output 2: sorted ws per GPU
    ##############################################
    sorted_gpupool_ws = sorted(ws_list['gpupool'][0], reverse=True)
    sorted_mig_ws = sorted(ws_list['mig'][0], reverse=True)
    sorted_heuristic_ws = sorted(ws_list['bw'][0], reverse=True)

    ws_csv = open('sorted_ws.csv', 'w')

    sorted_mig_ws = [str(ws) for ws in sorted_mig_ws]
    sorted_heuristic_ws = [str(ws) for ws in sorted_heuristic_ws]
    sorted_gpupool_ws = [str(ws) for ws in sorted_gpupool_ws]

    ws_csv.write('Heuristic,{}\n'.format(','.join(sorted_heuristic_ws)))
    ws_csv.write('Coarse,{}\n'.format(','.join(sorted_mig_ws)))
    ws_csv.write('GPUPool,{}\n'.format(','.join(sorted_gpupool_ws)))

    ws_csv.close()

    ##############################################
    # CSV file output 3: achieved QoS per job
    ##############################################
    job_ids = [job.id for job in batches[0].list_jobs]
    id_offset = batches[0].list_jobs[0].id

    def get_job_norm_sld(_violation):
        norm_sld = []
        for job_id in job_ids:
            job_qos = batches[0].list_jobs[job_id - id_offset].qos.value
            if job_id in _violation.job_sld:
                norm_sld.append(_violation.job_sld[job_id] / job_qos)
            else:
                norm_sld.append(1 / job_qos)

        return norm_sld

    norm_sld_gpupool = get_job_norm_sld(violation['gpupool'][0])
    norm_sld_mig = [job.sld_mig / job.qos.value for job in batches[0].list_jobs]
    norm_sld_heuristic = get_job_norm_sld(violation['bw'][0])

    xs = range(len(batches[0].list_jobs))

    # csv.write('xs, Coarse, Heuristic, GPUPool')
    scatter_data = np.array([np.array(xs),
                             np.array(norm_sld_mig),
                             np.array(norm_sld_heuristic),
                             np.array(norm_sld_gpupool)]).T

    np.savetxt('scatter.csv', scatter_data, delimiter=',')


if __name__ == '__main__':
    main()
