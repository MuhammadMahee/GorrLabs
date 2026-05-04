<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { createEventDispatcher, getContext } from 'svelte';
	const dispatch = createEventDispatcher();
	const i18n = getContext<Writable<i18nType>>('i18n');

	import XMark from '$lib/components/icons/XMark.svelte';
	import AdvancedParams from '../Settings/Advanced/AdvancedParams.svelte';
	import FileItem from '$lib/components/common/FileItem.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';

	import { user, settings } from '$lib/stores';
	export let models = [];
	$: void models;
	export let chatFiles = [];
	export let params: Record<string, any> = {};
	export let embed = false;

	// Persist collapsible section open/close state
	const getOpen = (key: string, fallback = true): boolean => {
		const v = localStorage.getItem(`chatControls.${key}`);
		return v !== null ? v === 'true' : fallback;
	};
	const setOpen = (key: string) => (open: boolean) => {
		localStorage.setItem(`chatControls.${key}`, String(open));
	};

	let showFiles = getOpen('files');
	let showSystemPrompt = getOpen('systemPrompt');
	let showAdvancedParams = getOpen('advancedParams');
</script>

<div class="h-full dark:text-gray-100">
	{#if !embed}
		<div
			class="mb-3 flex items-center justify-between border-b border-gray-200 px-1 pb-2 dark:border-white/[0.07]"
		>
			<div class="self-center font-primary text-[13px] font-semibold uppercase tracking-[0.08em] text-gray-500 dark:text-gray-400">
				{$i18n.t('Controls')}
			</div>
			<button
				class="self-center rounded-lg p-1.5 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:text-gray-500 dark:hover:bg-white/[0.06] dark:hover:text-white"
				aria-label={$i18n.t('Close chat controls')}
				on:click={() => {
					dispatch('close');
				}}
			>
				<XMark className="size-3.5" />
			</button>
		</div>
	{/if}

	{#if $user?.role === 'admin' || ($user?.permissions.chat?.controls ?? true)}
		<div class="space-y-3 pb-2 text-sm dark:text-gray-200">
			{#if chatFiles.length > 0}
				<section
					class="rounded-xl border border-gray-200 bg-white p-2 dark:border-white/[0.07] dark:bg-[#101116]/70"
				>
					<Collapsible
						title={$i18n.t('Files')}
						bind:open={showFiles}
						onChange={setOpen('files')}
						buttonClassName="w-full rounded-lg px-2 py-1.5 text-sm font-semibold text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.045]"
					>
						<div class="mt-2 flex flex-col gap-1" slot="content">
							{#each chatFiles as file, fileIdx}
								<FileItem
									className="w-full"
									item={file}
									edit={true}
									url={file?.url ? file.url : null}
									name={file.name}
									type={file.type}
									size={file?.size}
									dismissible={true}
									small={true}
									on:dismiss={() => {
										// Remove the file from the chatFiles array

										chatFiles.splice(fileIdx, 1);
										chatFiles = chatFiles;
									}}
									on:click={() => {
										console.log(file);
									}}
								/>
							{/each}
						</div>
					</Collapsible>
				</section>
			{/if}


			{#if $user?.role === 'admin'}
				<section
					class="rounded-xl border border-gray-200 bg-white p-2 dark:border-white/[0.07] dark:bg-[#101116]/70"
				>
					<Collapsible
						title={$i18n.t('System Prompt')}
						bind:open={showSystemPrompt}
						onChange={setOpen('systemPrompt')}
						buttonClassName="w-full rounded-lg px-2 py-1.5 text-sm font-semibold text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.045]"
					>
						<div class="pt-2" slot="content">
							<textarea
								bind:value={params.system}
								class="min-h-28 w-full resize-vertical rounded-xl border text-sm leading-6 outline-hidden transition focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/10 {$settings.highContrastMode
									? 'border-gray-300 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800'
									: 'border-gray-200 bg-gray-50/70 p-3 text-gray-900 placeholder:text-gray-400 dark:border-white/[0.08] dark:bg-[#0b0c11] dark:text-gray-100 dark:placeholder:text-gray-700'}"
								rows="4"
								placeholder={$i18n.t('Enter system prompt')}
							></textarea>
						</div>
					</Collapsible>
				</section>
			{/if}

			{#if $user?.role === 'admin' || ($user?.permissions.chat?.params ?? true)}
				<section
					class="rounded-xl border border-gray-200 bg-white p-2 dark:border-white/[0.07] dark:bg-[#101116]/70"
				>
					<Collapsible
						title={$i18n.t('Advanced Params')}
						bind:open={showAdvancedParams}
						onChange={setOpen('advancedParams')}
						buttonClassName="w-full rounded-lg px-2 py-1.5 text-sm font-semibold text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.045]"
					>
						<div class="mt-2" slot="content">
							<div class="rounded-xl border border-gray-200 bg-gray-50/70 p-1 dark:border-white/[0.06] dark:bg-[#0b0c11]">
								<AdvancedParams admin={$user?.role === 'admin'} custom={true} bind:params />
							</div>
						</div>
					</Collapsible>
				</section>
			{/if}
		</div>
	{/if}
</div>
