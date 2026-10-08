"""CSV 집계 결과를 표시함. 알려지지 않은 원본 수치에 곡선을 맞추지 않음."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_fig3(rows, panel, output, profile):
    fig, ax = plt.subplots(figsize=(7.2, 4.6), layout="constrained")
    groups = (
        sorted({(r["relays"], r["noise"]) for r in rows})
        if panel == "a"
        else sorted({r["noise"] for r in rows})
    )
    x_field = "total_length_km" if panel == "a" else "relays"
    for group in groups:
        selected = (
            [r for r in rows if (r["relays"], r["noise"]) == group]
            if panel == "a"
            else [r for r in rows if r["noise"] == group]
        )
        selected.sort(key=lambda r: r[x_field])
        # 0건은 로그 축에 표시할 수 없음. 임의의 양수로 대체하지 않음.
        points = [
            r for r in selected if panel != "a" or r["correct_sifted_bps_mean"] > 0
        ]
        if not points:
            continue
        label = f"{group[0]} relay(s), {group[1]}" if panel == "a" else group
        ax.errorbar(
            [r[x_field] for r in points],
            [r["correct_sifted_bps_mean"] for r in points],
            yerr=[r["correct_sifted_bps_sem"] or 0 for r in points],
            marker="o",
            capsize=3,
            label=label,
        )
    if panel == "a":
        ax.set_yscale("log")
    else:
        ax.set_xticks(sorted({r["relays"] for r in rows}))
    ax.set(
        xlabel="Total length (km)" if panel == "a" else "Trusted relays",
        ylabel="Correct-sifted bottleneck rate (bit/s)",
        title=f"Fig. 3({panel}) rerun | {profile}",
    )
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_fig5(rows, output, profile):
    fig, ax = plt.subplots(figsize=(7.2, 4.6), layout="constrained")
    for sessions in sorted({r["sessions"] for r in rows}):
        points = sorted(
            [r for r in rows if r["sessions"] == sessions],
            key=lambda r: r["send_rate_hz"],
        )
        ax.errorbar(
            [r["send_rate_hz"] for r in points],
            [r["mean_session_eps_mean"] for r in points],
            yerr=[r["mean_session_eps_sem"] or 0 for r in points],
            marker="o",
            capsize=3,
            label=f"{sessions} sessions",
        )
    ax.set(
        xlabel="Send rate per session (Hz)",
        ylabel="Mean per-session completion rate (pair/s)",
        title=f"Fig. 5 rerun | {profile}",
    )
    ax.grid(alpha=0.3)
    ax.legend()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_fig6(rows, path, metric):
    fig, ax = plt.subplots(figsize=(7.2, 4.6), layout='constrained')
    names = {'qubit': 'SimQN qubit', 'werner': 'SimQN Werner', 'netsquid': 'NetSquid DM'}
    for backend, workers in sorted({(r['backend'], r['workers']) for r in rows}):
        points = sorted([r for r in rows if (r['backend'], r['workers']) == (backend, workers)],
                        key=lambda r: r['nodes'])
        ax.errorbar([r['nodes'] for r in points], [r[f'{metric}_mean'] for r in points],
                    yerr=[r[f'{metric}_sem'] or 0 for r in points], capsize=3, marker='o',
                    label=f'{names[backend]} ({workers} process{"es" if workers != 1 else ""})')
    ax.set(xlabel='Nodes in linear chain',
           ylabel='Batch wall time / jobs (s)' if metric == 'amortized_seconds'
           else 'Individual job wall time (s)',
           title='Fig. 6 workload | measured times, mean + SEM')
    ax.grid(alpha=.3)
    ax.legend(fontsize=8)
    fig.savefig(path, dpi=160)
    plt.close(fig)
