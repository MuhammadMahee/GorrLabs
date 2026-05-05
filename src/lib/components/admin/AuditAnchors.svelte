<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	dayjs.extend(relativeTime);
	dayjs.extend(localizedFormat);

	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';
	import { ARKIVE_API_BASE_URL } from '$lib/constants';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import Pagination from '$lib/components/common/Pagination.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------

	let loaded = false;
	let anchors = null;
	let total = 0;
	let page = 1;
	const PAGE_SIZE = 50;

	let stats: { total: number; anchored: number; pending: number; by_event_type: Record<string, number> } | null = null;

	let filterType = '';
	let filterAnchored: '' | 'true' | 'false' = '';

	let verifyingId: string | null = null;
	let verifyResult: Record<string, { on_chain: boolean; memo?: string }> = {};

	// ---------------------------------------------------------------------------
	// API helpers
	// ---------------------------------------------------------------------------

	const fetchStats = async () => {
		const res = await fetch(`${ARKIVE_API_BASE_URL}/api/v1/audit/anchors/stats`, {
			headers: { Authorization: `Bearer ${localStorage.token}` }
		});
		if (!res.ok) throw new Error(await res.text());
		return res.json();
	};

	const fetchAnchors = async () => {
		const params = new URLSearchParams({
			page: String(page),
			page_size: String(PAGE_SIZE)
		});
		if (filterType) params.set('event_type', filterType);
		if (filterAnchored !== '') params.set('anchored', filterAnchored);

		const res = await fetch(`${ARKIVE_API_BASE_URL}/api/v1/audit/anchors?${params}`, {
			headers: { Authorization: `Bearer ${localStorage.token}` }
		});
		if (!res.ok) throw new Error(await res.text());
		return res.json();
	};

	const verifyAnchor = async (anchor_id: string) => {
		verifyingId = anchor_id;
		try {
			const res = await fetch(
				`${ARKIVE_API_BASE_URL}/api/v1/audit/anchors/${anchor_id}/verify`,
				{ headers: { Authorization: `Bearer ${localStorage.token}` } }
			);
			if (!res.ok) throw new Error(await res.text());
			const data = await res.json();
			verifyResult = { ...verifyResult, [anchor_id]: data };
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			verifyingId = null;
		}
	};

	// ---------------------------------------------------------------------------
	// Load / reactive
	// ---------------------------------------------------------------------------

	const load = async () => {
		try {
			const [s, a] = await Promise.all([fetchStats(), fetchAnchors()]);
			stats = s;
			anchors = a.anchors;
			total = a.total;
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	$: if (page || filterType !== undefined || filterAnchored !== undefined) {
		if (loaded) load();
	}

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
			return;
		}
		await load();
		loaded = true;
	});

	// ---------------------------------------------------------------------------
	// Helpers
	// ---------------------------------------------------------------------------

	const eventTypeBadgeColor = (et: string) => {
		const colors: Record<string, string> = {
			policy_decision: 'red',
			auth_event: 'blue',
			file_upload: 'yellow',
			model_call: 'purple',
			redaction: 'orange',
			feedback: 'green'
		};
		return colors[et] ?? 'gray';
	};

	const solanaExplorerUrl = (tx_id: string) =>
		`https://explorer.solana.com/tx/${tx_id}?cluster=testnet`;
</script>

{#if !loaded}
	<div class="flex items-center justify-center h-64">
		<Spinner />
	</div>
{:else}
	<div class="w-full pb-6 px-[16px] space-y-6">
		<!-- Header -->
		<div class="flex items-center justify-between mt-2">
			<div>
				<h2 class="text-lg font-semibold dark:text-white">{$i18n.t('Audit Anchors')}</h2>
				<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
					{$i18n.t('Solana on-chain audit trail — tamper-evident event hashes')}
				</p>
			</div>
		</div>

		<!-- Stats bar -->
		{#if stats}
			<div class="grid grid-cols-3 gap-3">
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-3"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Total')}</div>
					<div class="text-2xl font-bold dark:text-white mt-1">{stats.total.toLocaleString()}</div>
				</div>
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-3"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Anchored')}</div>
					<div class="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">
						{stats.anchored.toLocaleString()}
					</div>
				</div>
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 px-4 py-3"
				>
					<div class="text-xs text-gray-500 dark:text-gray-400">{$i18n.t('Pending')}</div>
					<div class="text-2xl font-bold text-yellow-500 dark:text-yellow-400 mt-1">
						{stats.pending.toLocaleString()}
					</div>
				</div>
			</div>
		{/if}

		<!-- Filters -->
		<div class="flex items-center gap-3">
			<input
				bind:value={filterType}
				on:input={() => { page = 1; }}
				placeholder={$i18n.t('Filter by event type…')}
				class="text-sm w-56 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 dark:text-white px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
			/>
			<select
				bind:value={filterAnchored}
				on:change={() => { page = 1; }}
				class="text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 dark:text-white px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
			>
				<option value="">{$i18n.t('All statuses')}</option>
				<option value="true">{$i18n.t('Anchored')}</option>
				<option value="false">{$i18n.t('Pending')}</option>
			</select>
		</div>

		<!-- Table -->
		{#if anchors === null}
			<div class="flex items-center justify-center h-40"><Spinner /></div>
		{:else if anchors.length === 0}
			<div class="text-center text-sm text-gray-400 dark:text-gray-500 py-12">
				{$i18n.t('No audit anchors found.')}
			</div>
		{:else}
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-800 overflow-hidden"
			>
				<table class="w-full text-sm text-left">
					<thead class="bg-gray-50 dark:bg-gray-800/60 text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">
						<tr>
							<th class="px-4 py-3">{$i18n.t('Event Type')}</th>
							<th class="px-4 py-3">{$i18n.t('Event ID')}</th>
							<th class="px-4 py-3">{$i18n.t('Hash')}</th>
							<th class="px-4 py-3">{$i18n.t('Status')}</th>
							<th class="px-4 py-3">{$i18n.t('Anchored')}</th>
							<th class="px-4 py-3">{$i18n.t('Created')}</th>
							<th class="px-4 py-3"></th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100 dark:divide-gray-800">
						{#each anchors as anchor (anchor.id)}
							<tr class="bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/40 transition">
								<td class="px-4 py-3">
									<Badge color={eventTypeBadgeColor(anchor.event_type)} content={anchor.event_type} />
								</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-300 font-mono text-xs max-w-[120px] truncate">
									<Tooltip content={anchor.event_id}>
										{anchor.event_id.length > 12 ? anchor.event_id.slice(0, 12) + '…' : anchor.event_id}
									</Tooltip>
								</td>
								<td class="px-4 py-3 font-mono text-xs text-gray-500 dark:text-gray-400 max-w-[120px] truncate">
									<Tooltip content={anchor.event_hash}>
										{anchor.event_hash.slice(0, 12)}…
									</Tooltip>
								</td>
								<td class="px-4 py-3">
									{#if anchor.tx_id}
										<Badge color="green" content="anchored" />
									{:else}
										<Badge color="yellow" content="pending" />
									{/if}
								</td>
								<td class="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
									{#if anchor.anchored_at}
										<Tooltip content={dayjs(anchor.anchored_at).format('LLL')}>
											{dayjs(anchor.anchored_at).fromNow()}
										</Tooltip>
									{:else}
										—
									{/if}
								</td>
								<td class="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
									<Tooltip content={dayjs(anchor.created_at).format('LLL')}>
										{dayjs(anchor.created_at).fromNow()}
									</Tooltip>
								</td>
								<td class="px-4 py-3 text-right space-x-2 whitespace-nowrap">
									{#if anchor.tx_id}
										<a
											href={solanaExplorerUrl(anchor.tx_id)}
											target="_blank"
											rel="noopener noreferrer"
											class="text-xs text-blue-500 hover:text-blue-600 underline"
										>
											{$i18n.t('Explorer')}
										</a>
										{#if verifyResult[anchor.id] !== undefined}
											{#if verifyResult[anchor.id].on_chain}
												<span class="text-xs text-green-600 dark:text-green-400 font-medium">✓ {$i18n.t('On-chain')}</span>
											{:else}
												<span class="text-xs text-red-500 font-medium">✗ {$i18n.t('Not found')}</span>
											{/if}
										{:else}
											<button
												class="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 underline"
												disabled={verifyingId === anchor.id}
												on:click={() => verifyAnchor(anchor.id)}
											>
												{verifyingId === anchor.id ? $i18n.t('Checking…') : $i18n.t('Verify')}
											</button>
										{/if}
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class="mt-2">
				<Pagination bind:page count={Math.ceil(total / PAGE_SIZE)} />
			</div>
		{/if}
	</div>
{/if}
