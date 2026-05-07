<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { goto } from '$app/navigation';
	import { ARKIVE_NAME, config } from '$lib/stores';
	import { onMount, getContext } from 'svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;

	onMount(async () => {
		if ($config) {
			await goto('/');
		}

		loaded = true;
	});
</script>

{#if loaded}
	<div class="arkive-page absolute w-full h-full flex z-50 text-gray-100">
		<div class="absolute rounded-xl w-full h-full backdrop-blur-sm flex justify-center">
			<div class="m-auto pb-44 flex flex-col justify-center">
				<div class="arkive-glass arkive-prism-ring max-w-md rounded-[28px] px-8 py-8">
					<div class="arkive-prism-text text-center text-2xl font-medium z-50">
						{$i18n.t('{{appName}} Backend Required', { appName: $ARKIVE_NAME })}
					</div>

					<div class=" mt-4 text-center text-sm w-full">
						{$i18n.t(
							"Oops! You're using an unsupported method (frontend only). Please serve Arkive from the backend."
						)}
					</div>

					<div class=" mt-6 mx-auto relative group w-fit">
						<button
							class="arkive-glow-btn relative z-20 flex px-5 py-2 rounded-full transition font-medium text-sm"
							on:click={() => {
								location.href = '/';
							}}
						>
							{$i18n.t('Check Again')}
						</button>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
