<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import Switch from '$lib/components/common/Switch.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import { getContext } from 'svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let onChange: (params: any) => void = () => {};

	export let admin = false;
	export let custom = false;

	const defaultParams = {
		stream_response: null,
		stream_delta_chunk_size: null,
		function_calling: null,
		reasoning_tags: null,
		seed: null,
		stop: null,
		temperature: null,
		reasoning_effort: null,
		logit_bias: null,
		max_tokens: null,
		top_k: null,
		top_p: null,
		min_p: null,
		frequency_penalty: null,
		presence_penalty: null,
		mirostat: null,
		mirostat_eta: null,
		mirostat_tau: null,
		repeat_last_n: null,
		tfs_z: null,
		repeat_penalty: null,
		use_mmap: null,
		use_mlock: null,
		think: null,
		format: null,
		keep_alive: null,
		num_keep: null,
		num_ctx: null,
		num_batch: null,
		num_thread: null,
		num_gpu: null
	};

	export let params: Record<string, any> = defaultParams;
	$: if (params) {
		onChange(params);
	}
</script>

<div class="advanced-params space-y-1 text-xs pb-safe-bottom">

	<!-- ── Temperature ── -->
	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t('Controls how creative or precise the response is. Higher = more creative, lower = more focused and predictable.')}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs">
					{$i18n.t('Temperature')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('creativity level')})</span>
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.temperature = (params?.temperature ?? null) === null ? 0.8 : null;
					}}
				>
					{#if (params?.temperature ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.temperature ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="0.05"
						bind:value={params.temperature}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.temperature}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<!-- ── Max Tokens ── -->
	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t('Sets the maximum length of the response. Higher values allow longer answers.')}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs">
					{$i18n.t('Max Tokens')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('response length limit')})</span>
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.max_tokens = (params?.max_tokens ?? null) === null ? 128 : null;
					}}
				>
					{#if (params?.max_tokens ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.max_tokens ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-2"
						max="131072"
						step="1"
						bind:value={params.max_tokens}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.max_tokens}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-2"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<!-- ── Top K ── -->
	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t('Limits word choices to the top K options at each step. Higher = more varied responses, lower = safer and more consistent.')}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs">
					{$i18n.t('Top K')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('quality of word choices')})</span>
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.top_k = (params?.top_k ?? null) === null ? 40 : null;
					}}
				>
					{#if (params?.top_k ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.top_k ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1000"
						step="0.5"
						bind:value={params.top_k}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.top_k}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="100"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<!-- ── Top P ── -->
	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t('Controls how focused the response stays on topic. Lower = more on-topic, higher = more diverse.')}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs">
					{$i18n.t('Top P')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('how focused the response stays')})</span>
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.top_p = (params?.top_p ?? null) === null ? 0.9 : null;
					}}
				>
					{#if (params?.top_p ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.top_p ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.top_p}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.top_p}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<!-- ── Admin-only params ── -->
	{#if admin}

		<div>
			<Tooltip
				content={$i18n.t('When enabled, the model will respond to each chat message in real-time, generating a response as soon as the user sends a message.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs">
						{$i18n.t('Stream Chat Response')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('send response word by word as it generates')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						on:click={() => {
							params.stream_response =
								(params?.stream_response ?? null) === null
									? true
									: params.stream_response
										? false
										: null;
						}}
						type="button"
					>
						{#if params.stream_response === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else if params.stream_response === false}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>
		</div>

		<div>
			<Tooltip
				content={$i18n.t('The stream delta chunk size for the model.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{$i18n.t('Stream Delta Chunk Size')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('how many words are sent per chunk')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.stream_delta_chunk_size =
								(params?.stream_delta_chunk_size ?? null) === null ? 1 : null;
						}}
					>
						{#if (params?.stream_delta_chunk_size ?? null) === null}
							<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
						{:else}
							<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.stream_delta_chunk_size ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="1"
							max="128"
							step="1"
							bind:value={params.stream_delta_chunk_size}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.stream_delta_chunk_size}
							type="number"
							class=" bg-transparent text-center w-14"
							min="1"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div>
			<Tooltip
				content={$i18n.t("Default mode works with a wider range of models by calling tools once before execution. Native mode leverages the model's built-in tool-calling capabilities.")}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs">
						{$i18n.t('Function Calling')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('how the model uses tools and functions')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						on:click={() => {
							params.function_calling = (params?.function_calling ?? null) === null ? 'native' : null;
						}}
						type="button"
					>
						{#if params.function_calling === 'native'}
							<span class="ml-2 self-center">{$i18n.t('Native')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Enable, disable, or customize the reasoning tags used by the model.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{$i18n.t('Reasoning Tags')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('tags that wrap the model thinking steps')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							if ((params?.reasoning_tags ?? null) === null) {
								params.reasoning_tags = ['', ''];
							} else if ((params?.reasoning_tags ?? []).length === 2) {
								params.reasoning_tags = true;
							} else if ((params?.reasoning_tags ?? null) !== false) {
								params.reasoning_tags = false;
							} else {
								params.reasoning_tags = null;
							}
						}}
					>
						{#if (params?.reasoning_tags ?? null) === null}
							<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
						{:else if (params?.reasoning_tags ?? null) === true}
							<span class="ml-2 self-center"> {$i18n.t('Enabled')} </span>
						{:else if (params?.reasoning_tags ?? null) === false}
							<span class="ml-2 self-center"> {$i18n.t('Disabled')} </span>
						{:else}
							<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if ![true, false, null].includes(params?.reasoning_tags ?? null) && (params?.reasoning_tags ?? []).length === 2}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							class="text-sm w-full bg-transparent outline-hidden outline-none"
							type="text"
							placeholder={$i18n.t('Start Tag')}
							bind:value={params.reasoning_tags[0]}
							autocomplete="off"
						/>
					</div>
					<div class=" flex-1">
						<input
							class="text-sm w-full bg-transparent outline-hidden outline-none"
							type="text"
							placeholder={$i18n.t('End Tag')}
							bind:value={params.reasoning_tags[1]}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Sets the random number seed. Setting this to a specific number makes the model generate the same text for the same prompt.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{$i18n.t('Seed')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('fixed value for reproducible responses')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.seed = (params?.seed ?? null) === null ? 0 : null;
						}}
					>
						{#if (params?.seed ?? null) === null}
							<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
						{:else}
							<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.seed ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							class="text-sm w-full bg-transparent outline-hidden outline-none"
							type="number"
							placeholder={$i18n.t('Enter Seed')}
							bind:value={params.seed}
							autocomplete="off"
							min="0"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Sets the stop sequences to use. When this pattern is encountered, the LLM will stop generating text.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{$i18n.t('Stop Sequence')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('text pattern that ends the response early')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.stop = (params?.stop ?? null) === null ? '' : null;
						}}
					>
						{#if (params?.stop ?? null) === null}
							<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
						{:else}
							<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.stop ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							class="text-sm w-full bg-transparent outline-hidden outline-none"
							type="text"
							placeholder={$i18n.t('Enter stop sequence')}
							bind:value={params.stop}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Constrains effort on reasoning for reasoning models. Only applicable to reasoning models from specific providers that support reasoning effort.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{$i18n.t('Reasoning Effort')} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('how much time the model spends thinking')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.reasoning_effort = (params?.reasoning_effort ?? null) === null ? 'medium' : null;
						}}
					>
						{#if (params?.reasoning_effort ?? null) === null}
							<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
						{:else}
							<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.reasoning_effort ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							class="text-sm w-full bg-transparent outline-hidden outline-none"
							type="text"
							placeholder={$i18n.t('Enter reasoning effort')}
							bind:value={params.reasoning_effort}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Boosting or penalizing specific tokens for constrained responses. (Default: none)')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'logit_bias'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('boost or suppress specific words')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.logit_bias = (params?.logit_bias ?? null) === null ? '' : null;
						}}
					>
						{#if (params?.logit_bias ?? null) === null}
							<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
						{:else}
							<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.logit_bias ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							class="text-sm w-full bg-transparent outline-hidden outline-none"
							type="text"
							placeholder={$i18n.t('Enter comma-separated "token:bias_value" pairs (example: 5432:100, 413:-100)')}
							bind:value={params.logit_bias}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Alternative to top_p. Sets the minimum probability for a token relative to the most likely token.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'min_p'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('minimum word probability filter')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.min_p = (params?.min_p ?? null) === null ? 0.0 : null;
						}}
					>
						{#if (params?.min_p ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.min_p ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="0"
							max="1"
							step="0.05"
							bind:value={params.min_p}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.min_p}
							type="number"
							class=" bg-transparent text-center w-14"
							min="0"
							max="1"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Penalizes tokens based on how many times they have appeared. Higher values reduce repetition.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'frequency_penalty'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('reduce word repetition')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.frequency_penalty = (params?.frequency_penalty ?? null) === null ? 1.1 : null;
						}}
					>
						{#if (params?.frequency_penalty ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.frequency_penalty ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="-2"
							max="2"
							step="0.05"
							bind:value={params.frequency_penalty}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.frequency_penalty}
							type="number"
							class=" bg-transparent text-center w-14"
							min="-2"
							max="2"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Penalizes tokens that have appeared at least once, regardless of frequency.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'presence_penalty'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('encourage new topics')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded transition flex-shrink-0 outline-none"
						type="button"
						on:click={() => {
							params.presence_penalty = (params?.presence_penalty ?? null) === null ? 0.0 : null;
						}}
					>
						{#if (params?.presence_penalty ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.presence_penalty ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="-2"
							max="2"
							step="0.05"
							bind:value={params.presence_penalty}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.presence_penalty}
							type="number"
							class=" bg-transparent text-center w-14"
							min="-2"
							max="2"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Enable Mirostat sampling for controlling perplexity.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'mirostat'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('adaptive output quality control')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.mirostat = (params?.mirostat ?? null) === null ? 0 : null;
						}}
					>
						{#if (params?.mirostat ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.mirostat ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="0"
							max="2"
							step="1"
							bind:value={params.mirostat}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.mirostat}
							type="number"
							class=" bg-transparent text-center w-14"
							min="0"
							max="2"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Mirostat learning rate — how quickly the algorithm responds to feedback from generated text.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'mirostat_eta'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('quality control learning speed')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.mirostat_eta = (params?.mirostat_eta ?? null) === null ? 0.1 : null;
						}}
					>
						{#if (params?.mirostat_eta ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.mirostat_eta ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="0"
							max="1"
							step="0.05"
							bind:value={params.mirostat_eta}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.mirostat_eta}
							type="number"
							class=" bg-transparent text-center w-14"
							min="0"
							max="1"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Controls the balance between coherence and diversity of the output.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'mirostat_tau'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('quality vs diversity balance')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.mirostat_tau = (params?.mirostat_tau ?? null) === null ? 5.0 : null;
						}}
					>
						{#if (params?.mirostat_tau ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.mirostat_tau ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="0"
							max="10"
							step="0.5"
							bind:value={params.mirostat_tau}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.mirostat_tau}
							type="number"
							class=" bg-transparent text-center w-14"
							min="0"
							max="10"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Sets how far back the model looks to prevent repetition.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'repeat_last_n'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('repetition look-back window')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.repeat_last_n = (params?.repeat_last_n ?? null) === null ? 64 : null;
						}}
					>
						{#if (params?.repeat_last_n ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.repeat_last_n ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="-1"
							max="128"
							step="1"
							bind:value={params.repeat_last_n}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.repeat_last_n}
							type="number"
							class=" bg-transparent text-center w-14"
							min="-1"
							max="128"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Tail free sampling — reduces the impact of less probable tokens. Higher = more reduction.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'tfs_z'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('filter low-probability tokens')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.tfs_z = (params?.tfs_z ?? null) === null ? 1 : null;
						}}
					>
						{#if (params?.tfs_z ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.tfs_z ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="0"
							max="2"
							step="0.05"
							bind:value={params.tfs_z}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.tfs_z}
							type="number"
							class=" bg-transparent text-center w-14"
							min="0"
							max="2"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Penalizes token sequences to reduce repetition. Higher values penalize more strongly.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'repeat_penalty'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('penalize repeated phrases')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded transition flex-shrink-0 outline-none"
						type="button"
						on:click={() => {
							params.repeat_penalty = (params?.repeat_penalty ?? null) === null ? 1.1 : null;
						}}
					>
						{#if (params?.repeat_penalty ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.repeat_penalty ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="-2"
							max="2"
							step="0.05"
							bind:value={params.repeat_penalty}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.repeat_penalty}
							type="number"
							class=" bg-transparent text-center w-14"
							min="-2"
							max="2"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Enable Memory Mapping to load model data from disk as if it were in RAM.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'use_mmap'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('use disk as extra RAM')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.use_mmap = (params?.use_mmap ?? null) === null ? true : null;
						}}
					>
						{#if (params?.use_mmap ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.use_mmap ?? null) !== null}
				<div class="flex justify-between items-center mt-1">
					<div class="text-xs text-gray-500">
						{params.use_mmap ? $i18n.t('Enabled') : $i18n.t('Disabled')}
					</div>
					<div class=" pr-2">
						<Switch bind:state={params.use_mmap} />
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t("Enable Memory Locking to prevent model data from being swapped out of RAM.")}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'use_mlock'} <span class="text-gray-400 dark:text-gray-500">({$i18n.t('lock model in RAM')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.use_mlock = (params?.use_mlock ?? null) === null ? true : null;
						}}
					>
						{#if (params?.use_mlock ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.use_mlock ?? null) !== null}
				<div class="flex justify-between items-center mt-1">
					<div class="text-xs text-gray-500">
						{params.use_mlock ? $i18n.t('Enabled') : $i18n.t('Disabled')}
					</div>
					<div class=" pr-2">
						<Switch bind:state={params.use_mlock} />
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Enables or disables the thinking/reasoning feature in Ollama before generating a response.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs">
						{'think'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('model thinks before answering')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						on:click={() => {
							if ((params?.think ?? null) === null) {
								params.think = true;
							} else if (params.think === true) {
								params.think = 'medium';
							} else if (typeof params.think === 'string') {
								params.think = false;
							} else {
								params.think = null;
							}
						}}
						type="button"
					>
						{#if params.think === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else if params.think === false}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{:else if typeof params.think === 'string'}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if typeof params.think === 'string'}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							class="text-sm w-full bg-transparent outline-hidden outline-none"
							type="text"
							placeholder={$i18n.t("e.g. 'low', 'medium', 'high'")}
							bind:value={params.think}
							autocomplete="off"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('The format to return a response in. Format can be json or a JSON schema.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs">
						{'format'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('force a specific output format')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						on:click={() => {
							params.format = (params?.format ?? null) === null ? 'json' : null;
						}}
						type="button"
					>
						{#if (params?.format ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('JSON')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.format ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<Textarea
						className="w-full text-sm bg-transparent outline-hidden"
						placeholder={$i18n.t('e.g. "json" or a JSON schema')}
						bind:value={params.format}
					/>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Controls how many tokens are preserved when refreshing the context.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'num_keep'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('context tokens to preserve')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.num_keep = (params?.num_keep ?? null) === null ? 24 : null;
						}}
					>
						{#if (params?.num_keep ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.num_keep ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="-1"
							max="10240000"
							step="1"
							bind:value={params.num_keep}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div class="">
						<input
							bind:value={params.num_keep}
							type="number"
							class=" bg-transparent text-center w-14"
							min="-1"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Sets the size of the context window used to generate the next token.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'num_ctx'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('context window size')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.num_ctx = (params?.num_ctx ?? null) === null ? 2048 : null;
						}}
					>
						{#if (params?.num_ctx ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.num_ctx ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="-1"
							max="10240000"
							step="1"
							bind:value={params.num_ctx}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div class="">
						<input
							bind:value={params.num_ctx}
							type="number"
							class=" bg-transparent text-center w-14"
							min="-1"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Determines how many text requests are processed together. Higher = faster but uses more memory.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'num_batch'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('processing batch size')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.num_batch = (params?.num_batch ?? null) === null ? 512 : null;
						}}
					>
						{#if (params?.num_batch ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.num_batch ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="256"
							max="8192"
							step="256"
							bind:value={params.num_batch}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.num_batch}
							type="number"
							class=" bg-transparent text-center w-14"
							min="256"
							step="256"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Number of worker threads used for computation.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'num_thread'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('CPU threads to use')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.num_thread = (params?.num_thread ?? null) === null ? 2 : null;
						}}
					>
						{#if (params?.num_thread ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.num_thread ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="1"
							max="256"
							step="1"
							bind:value={params.num_thread}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div class="">
						<input
							bind:value={params.num_thread}
							type="number"
							class=" bg-transparent text-center w-14"
							min="1"
							max="256"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('Number of model layers to offload to GPU.')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs">
						{'num_gpu'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('GPU layers to offload')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.num_gpu = (params?.num_gpu ?? null) === null ? 0 : null;
						}}
					>
						{#if (params?.num_gpu ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.num_gpu ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="0"
							max="256"
							step="1"
							bind:value={params.num_gpu}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div class="">
						<input
							bind:value={params.num_gpu}
							type="number"
							class=" bg-transparent text-center w-14"
							min="0"
							max="256"
							step="1"
						/>
					</div>
				</div>
			{/if}
		</div>

		<div class=" py-0.5 w-full justify-between">
			<Tooltip
				content={$i18n.t('How long the model stays loaded in memory after the last request. (default: 5m)')}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs">
						{'keep_alive'} ({$i18n.t('Ollama')}) <span class="text-gray-400 dark:text-gray-500">({$i18n.t('how long model stays in memory')})</span>
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						on:click={() => {
							params.keep_alive = (params?.keep_alive ?? null) === null ? '5m' : null;
						}}
						type="button"
					>
						{#if (params?.keep_alive ?? null) === null}
							<span class="ml-2 self-center">{$i18n.t('Default')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.keep_alive ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<input
						class="w-full text-sm bg-transparent outline-hidden"
						type="text"
						placeholder={$i18n.t("e.g. '30s','10m'. Valid time units are 's', 'm', 'h'.")}
						bind:value={params.keep_alive}
					/>
				</div>
			{/if}
		</div>

		{#if custom}
			<div class="flex flex-col justify-center">
				{#each Object.keys(params?.custom_params ?? {}) as key}
					<div class=" py-0.5 w-full justify-between mb-1">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs">
								<input
									type="text"
									class=" text-xs w-full bg-transparent outline-none"
									placeholder={$i18n.t('Custom Parameter Name')}
									value={key}
									on:change={(e) => {
										const newKey = (e.target as HTMLInputElement).value.trim();
										if (newKey && newKey !== key) {
											params.custom_params[newKey] = params.custom_params[key];
											delete params.custom_params[key];
											params = {
												...params,
												custom_params: { ...params.custom_params }
											};
										}
									}}
								/>
							</div>
							<button
								class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
								type="button"
								on:click={() => {
									delete params.custom_params[key];
									params = {
										...params,
										custom_params: { ...params.custom_params }
									};
								}}
							>
								{$i18n.t('Remove')}
							</button>
						</div>
						<div class="flex mt-0.5 space-x-2">
							<div class=" flex-1">
								<input
									bind:value={params.custom_params[key]}
									type="text"
									class="text-sm w-full bg-transparent outline-hidden outline-none"
									placeholder={$i18n.t('Custom Parameter Value')}
								/>
							</div>
						</div>
					</div>
				{/each}

				<button
					class=" flex gap-2 items-center w-full text-center justify-center mt-1 mb-5"
					type="button"
					on:click={() => {
						params.custom_params = (params?.custom_params ?? {}) || {};
						params.custom_params['custom_param_name'] = 'custom_param_value';
					}}
				>
					<div>
						<Plus />
					</div>
					<div>{$i18n.t('Add Custom Parameter')}</div>
				</button>
			</div>
		{/if}

	{/if}
	<!-- end admin -->

</div>

<style>
	.advanced-params {
		color: rgb(226, 232, 240);
	}

	.advanced-params > div {
		border: 1px solid transparent;
		border-radius: 0.625rem;
		padding: 0.5rem 0.625rem;
		transition:
			background-color 150ms ease,
			border-color 150ms ease;
	}

	.advanced-params > div:hover {
		border-color: rgba(255, 255, 255, 0.055);
		background: rgba(255, 255, 255, 0.025);
	}

	.advanced-params :global(.inline-tooltip) {
		display: block;
		width: 100%;
	}

	.advanced-params :global(.inline-tooltip > div) {
		width: 100%;
	}

	.advanced-params :global(.inline-tooltip > div > div) {
		align-items: center;
		gap: 0.875rem;
		min-height: 2.25rem;
	}

	.advanced-params :global(.inline-tooltip > div > div > div:first-child) {
		max-width: calc(100% - 5.75rem);
		color: rgb(214, 223, 237);
		font-size: 0.78rem;
		font-weight: 600;
		line-height: 1.05rem;
	}

	.advanced-params :global(.inline-tooltip > div > div > div:first-child span) {
		display: block;
		margin-top: 0.125rem;
		color: rgb(100, 116, 139) !important;
		font-size: 0.72rem;
		font-weight: 500;
		line-height: 0.95rem;
	}

	.advanced-params button {
		min-width: 4.5rem;
		min-height: 1.9rem;
		justify-content: center;
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 0.625rem;
		background: rgba(255, 255, 255, 0.04);
		color: rgb(226, 232, 240);
		font-size: 0.72rem;
		font-weight: 700;
	}

	.advanced-params button:hover {
		border-color: rgba(34, 211, 238, 0.25);
		background: rgba(34, 211, 238, 0.08);
		color: white;
	}

	.advanced-params button span {
		margin-left: 0;
	}

	.advanced-params input[type='number'] {
		width: 4rem;
		border-radius: 0.625rem;
		border: 1px solid rgba(255, 255, 255, 0.07);
		background: rgba(255, 255, 255, 0.04);
		padding: 0.25rem 0.375rem;
		color: rgb(226, 232, 240);
		font-weight: 700;
	}

	.advanced-params input[type='range'] {
		accent-color: rgb(34, 211, 238);
	}

	.advanced-params input[type='range']::-webkit-slider-runnable-track {
		height: 0.375rem;
		border-radius: 9999px;
		background: rgba(51, 65, 85, 0.8);
	}

	.advanced-params input[type='range']::-webkit-slider-thumb {
		margin-top: -0.3rem;
	}
</style>
