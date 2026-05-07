<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { Switch } from 'bits-ui';

	import { createEventDispatcher, tick, getContext } from 'svelte';
	import { settings } from '$lib/stores';

	import Tooltip from './Tooltip.svelte';
	export let state = true;
	export let id = '';
	export let ariaLabelledbyId = '';
	export let tooltip = false;

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher();
</script>

<Tooltip
	content={typeof tooltip === 'string'
		? tooltip
		: typeof tooltip === 'boolean' && tooltip
			? state
				? $i18n.t('Enabled')
				: $i18n.t('Disabled')
			: ''}
	placement="top"
>
	<Switch.Root
		bind:checked={state}
		{id}
		aria-labelledby={ariaLabelledbyId}
		class="arkive-switch flex h-[1.25rem] min-h-[1.25rem] w-9 shrink-0 cursor-pointer items-center rounded-full px-1 mx-[1px] transition  {($settings?.highContrastMode ??
		false)
			? 'focus:outline focus:outline-2 focus:outline-gray-800 focus:dark:outline-gray-200'
			: 'outline outline-1 outline-gray-200 dark:outline-white/10'} {state
			? ' bg-emerald-500 dark:bg-emerald-500'
			: 'bg-gray-200 dark:bg-white/[0.055]'}"
		onCheckedChange={async () => {
			await tick();
			dispatch('change', state);
		}}
	>
		<Switch.Thumb
			class="pointer-events-none block size-3 shrink-0 rounded-full bg-white transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0 data-[state=unchecked]:bg-gray-500 data-[state=unchecked]:shadow-mini "
		/>
	</Switch.Root>
</Tooltip>
