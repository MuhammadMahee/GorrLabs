<script lang="ts">
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext, tick } from 'svelte';

	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import DropdownSub from '$lib/components/common/DropdownSub.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import DocumentDuplicate from '$lib/components/icons/DocumentDuplicate.svelte';
	import Bookmark from '$lib/components/icons/Bookmark.svelte';
	import BookmarkSlash from '$lib/components/icons/BookmarkSlash.svelte';
	import {
		getChatById,
		getChatPinnedStatusById,
		toggleChatPinnedStatusById
	} from '$lib/apis/chats';
	import { chats, folders, settings, user } from '$lib/stores';
	import { createMessagesList } from '$lib/utils';
	import { downloadChatAsPDF } from '$lib/apis/utils';
	import Download from '$lib/components/icons/Download.svelte';
	import Folder from '$lib/components/icons/Folder.svelte';
	import Messages from '$lib/components/chat/Messages.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let moveChatHandler: Function;

	export let cloneChatHandler: Function;
	export let archiveChatHandler: Function;
	export let renameHandler: Function;
	export let deleteHandler: Function;
	export let onClose: Function;

	export let chatId = '';

	let show = false;
	let pinned = false;

	let chat = null;
	let showFullMessages = false;

	export let onPinChange: () => void = () => {};

	const pinHandler = async () => {
		await toggleChatPinnedStatusById(localStorage.token, chatId);
		onPinChange();
	};

	const checkPinned = async () => {
		pinned = await getChatPinnedStatusById(localStorage.token, chatId);
	};

	const getChatAsText = async (chat) => {
		const history = chat.chat.history;
		const messages = createMessagesList(history, history.currentId);
		const chatText = messages.reduce((a, message, i, arr) => {
			return `${a}### ${message.role.toUpperCase()}\n${message.content}\n\n`;
		}, '');

		return chatText.trim();
	};

	const downloadTxt = async () => {
		const chat = await getChatById(localStorage.token, chatId);
		if (!chat) {
			return;
		}

		const chatText = await getChatAsText(chat);
		let blob = new Blob([chatText], {
			type: 'text/plain'
		});

		saveAs(blob, `chat-${chat.chat.title}.txt`);
	};

	const downloadPdf = async () => {
		chat = await getChatById(localStorage.token, chatId);
		if (!chat) {
			return;
		}

		const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
			import('jspdf'),
			import('html2canvas-pro')
		]);

		if ($settings?.stylizedPdfExport ?? true) {
			showFullMessages = true;
			await tick();

			const containerElement = document.getElementById('full-messages-container');
			if (containerElement) {
				try {
					const isDarkMode = document.documentElement.classList.contains('dark');
					const virtualWidth = 800; // px, fixed width for cloned element

					// Clone and style
					const clonedElement = containerElement.cloneNode(true) as HTMLElement;
					clonedElement.classList.add('text-black');
					clonedElement.classList.add('dark:text-white');
					clonedElement.style.width = `${virtualWidth}px`;
					clonedElement.style.position = 'absolute';
					clonedElement.style.left = '-9999px';
					clonedElement.style.height = 'auto';
					document.body.appendChild(clonedElement);

					// Wait for DOM update/layout
					await new Promise((r) => setTimeout(r, 100));

					// Render entire content once
					const canvas = await html2canvas(clonedElement, {
						backgroundColor: isDarkMode ? '#000' : '#fff',
						useCORS: true,
						scale: 2, // increase resolution
						width: virtualWidth
					});

					document.body.removeChild(clonedElement);

					const pdf = new jsPDF('p', 'mm', 'a4');
					const pageWidthMM = 210;
					const pageHeightMM = 297;

					// Convert page height in mm to px on canvas scale for cropping
					// Get canvas DPI scale:
					const pxPerMM = canvas.width / virtualWidth; // width in px / width in px?
					// Since 1 page width is 210 mm, but canvas width is 800 px at scale 2
					// Assume 1 mm = px / (pageWidthMM scaled)
					// Actually better: Calculate scale factor from px/mm:
					// virtualWidth px corresponds directly to 210mm in PDF, so pxPerMM:
					const pxPerPDFMM = canvas.width / pageWidthMM; // canvas px per PDF mm

					// Height in px for one page slice:
					const pagePixelHeight = Math.floor(pxPerPDFMM * pageHeightMM);

					let offsetY = 0;
					let page = 0;

					while (offsetY < canvas.height) {
						// Height of slice
						const sliceHeight = Math.min(pagePixelHeight, canvas.height - offsetY);

						// Create temp canvas for slice
						const pageCanvas = document.createElement('canvas');
						pageCanvas.width = canvas.width;
						pageCanvas.height = sliceHeight;

						const ctx = pageCanvas.getContext('2d');

						// Draw the slice of original canvas onto pageCanvas
						ctx.drawImage(
							canvas,
							0,
							offsetY,
							canvas.width,
							sliceHeight,
							0,
							0,
							canvas.width,
							sliceHeight
						);

						const imgData = pageCanvas.toDataURL('image/jpeg', 0.7);

						// Calculate image height in PDF units keeping aspect ratio
						const imgHeightMM = (sliceHeight * pageWidthMM) / canvas.width;

						if (page > 0) pdf.addPage();

						if (isDarkMode) {
							pdf.setFillColor(0, 0, 0);
							pdf.rect(0, 0, pageWidthMM, pageHeightMM, 'F'); // black bg
						}

						pdf.addImage(imgData, 'JPEG', 0, 0, pageWidthMM, imgHeightMM);

						offsetY += sliceHeight;
						page++;
					}

					pdf.save(`chat-${chat.chat.title}.pdf`);

					showFullMessages = false;
				} catch (error) {
					console.error('Error generating PDF', error);
				}
			}
		} else {
			console.log('Downloading PDF');

			const chatText = await getChatAsText(chat);

			const doc = new jsPDF();

			// Margins
			const left = 15;
			const top = 20;
			const right = 15;
			const bottom = 20;

			const pageWidth = doc.internal.pageSize.getWidth();
			const pageHeight = doc.internal.pageSize.getHeight();
			const usableWidth = pageWidth - left - right;
			const usableHeight = pageHeight - top - bottom;

			// Font size and line height
			const fontSize = 8;
			doc.setFontSize(fontSize);
			const lineHeight = fontSize * 1; // adjust if needed

			// Split the markdown into lines (handles \n)
			const paragraphs = chatText.split('\n');

			let y = top;

			for (let paragraph of paragraphs) {
				// Wrap each paragraph to fit the width
				const lines = doc.splitTextToSize(paragraph, usableWidth);

				for (let line of lines) {
					// If the line would overflow the bottom, add a new page
					if (y + lineHeight > pageHeight - bottom) {
						doc.addPage();
						y = top;
					}
					doc.text(line, left, y);
					y += lineHeight * 0.5;
				}
				// Add empty line at paragraph breaks
				y += lineHeight * 0.1;
			}

			doc.save(`chat-${chat.chat.title}.pdf`);
		}
	};

	const downloadJSONExport = async () => {
		const chat = await getChatById(localStorage.token, chatId);

		if (chat) {
			let blob = new Blob([JSON.stringify([chat])], {
				type: 'application/json'
			});
			saveAs(blob, `chat-export-${Date.now()}.json`);
		}
	};

	$: if (show) {
		checkPinned();
	}
</script>

{#if chat && showFullMessages}
	<div class="hidden w-full h-full flex-col">
		<div id="full-messages-container">
			<Messages
				className="h-full flex pt-4 pb-8 w-full"
				chatId={`chat-preview-${chat?.id ?? ''}`}
				user={$user}
				readOnly={true}
				history={chat.chat.history}
				autoScroll={true}
				sendMessage={() => {}}
				messagesCount={null}
				editCodeBlock={false}
			/>
		</div>
	</div>
{/if}

<Dropdown
	bind:show
	onOpenChange={(state) => {
		if (state === false) {
			onClose();
		}
	}}
>
	<Tooltip content={$i18n.t('More')}>
		<slot />
	</Tooltip>

	<div slot="content">
		<div
			class="z-50 min-w-[220px] select-none rounded-2xl border border-gray-200 bg-white/95 p-1.5 text-sm text-gray-900 shadow-2xl shadow-black/10 backdrop-blur-xl transition dark:border-white/[0.08] dark:bg-[#080a10]/95 dark:text-white dark:shadow-black/40"
		>
			<DropdownSub
				contentClass="select-none rounded-2xl p-1.5 z-50 bg-white/95 dark:bg-[#080a10]/95 dark:text-white shadow-2xl shadow-black/10 dark:shadow-black/40 border border-gray-200 dark:border-white/[0.08] backdrop-blur-xl"
			>
				<button
					slot="trigger"
					draggable="false"
					class="flex h-10 w-full cursor-pointer items-center gap-3 rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				>
					<div class="flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
						<Download strokeWidth="1.5" />
					</div>
					<div class="flex items-center font-medium">{$i18n.t('Download')}</div>
				</button>

				{#if $user?.role === 'admin' || ($user.permissions?.chat?.export ?? true)}
					<button
						draggable="false"
						class="flex h-9 w-full cursor-pointer items-center rounded-xl px-3 text-sm text-gray-700 transition hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-white/[0.055]"
						on:click={() => {
							downloadJSONExport();
						}}
					>
						<div class="flex items-center line-clamp-1">{$i18n.t('Export chat (.json)')}</div>
					</button>
				{/if}

				<button
					draggable="false"
					class="flex h-9 w-full cursor-pointer items-center rounded-xl px-3 text-sm text-gray-700 transition hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-white/[0.055]"
					on:click={() => {
						downloadTxt();
					}}
				>
					<div class="flex items-center line-clamp-1">{$i18n.t('Plain text (.txt)')}</div>
				</button>

				<button
					draggable="false"
					class="flex h-9 w-full cursor-pointer select-none items-center rounded-xl px-3 text-sm text-gray-700 transition hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-white/[0.055]"
					on:click={() => {
						downloadPdf();
					}}
				>
					<div class="flex items-center line-clamp-1">{$i18n.t('PDF document (.pdf)')}</div>
				</button>
			</DropdownSub>

			<button
				draggable="false"
				class="flex h-10 w-full cursor-pointer items-center gap-3 rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				on:click={() => {
					renameHandler();
				}}
			>
				<div class="flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
					<Pencil strokeWidth="1.5" />
				</div>
				<div class="flex items-center font-medium">{$i18n.t('Rename')}</div>
			</button>

			<hr class="my-1 border-gray-100 p-0 dark:border-white/[0.06]" />

			<button
				draggable="false"
				class="flex h-10 w-full cursor-pointer items-center gap-3 rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				on:click={() => {
					pinHandler();
				}}
			>
				{#if pinned}
					<div class="flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
						<BookmarkSlash strokeWidth="1.5" />
					</div>
					<div class="flex items-center font-medium">{$i18n.t('Unpin')}</div>
				{:else}
					<div class="flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
						<Bookmark strokeWidth="1.5" />
					</div>
					<div class="flex items-center font-medium">{$i18n.t('Pin')}</div>
				{/if}
			</button>

			<button
				draggable="false"
				class="flex h-10 w-full cursor-pointer items-center gap-3 rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				on:click={() => {
					show = false;
					cloneChatHandler();
				}}
			>
				<div class="flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
					<DocumentDuplicate strokeWidth="1.5" />
				</div>
				<div class="flex items-center font-medium">{$i18n.t('Clone')}</div>
			</button>

			{#if chatId && $folders.length > 0}
				<DropdownSub
					contentClass="select-none rounded-2xl p-1.5 z-50 bg-white/95 dark:bg-[#080a10]/95 dark:text-white border border-gray-200 dark:border-white/[0.08] shadow-2xl shadow-black/10 dark:shadow-black/40 max-h-52 overflow-y-auto scrollbar-hidden backdrop-blur-xl"
				>
					<button
						slot="trigger"
						draggable="false"
						class="flex h-10 w-full cursor-pointer select-none items-center gap-3 rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
					>
						<div class="flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
							<Folder />
						</div>
						<div class="flex items-center font-medium">{$i18n.t('Move')}</div>
					</button>

					{#each $folders.sort((a, b) => b.updated_at - a.updated_at) as folder}
						<button
							draggable="false"
							class="flex h-9 w-full cursor-pointer items-center gap-2 overflow-hidden rounded-xl px-3 text-sm text-gray-700 transition hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-white/[0.055]"
							on:click={() => {
								moveChatHandler(chatId, folder.id);
							}}
						>
							<div class="shrink-0">
								<Folder />
							</div>

							<div class="truncate">{folder?.name ?? 'Folder'}</div>
						</button>
					{/each}
				</DropdownSub>
			{/if}

			<button
				draggable="false"
				class="flex h-10 w-full cursor-pointer items-center gap-3 rounded-xl px-3 text-gray-800 transition hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-white/[0.055]"
				on:click={() => {
					archiveChatHandler();
				}}
			>
				<div class="flex size-5 items-center justify-center text-gray-500 dark:text-gray-400">
					<ArchiveBox strokeWidth="1.5" />
				</div>
				<div class="flex items-center font-medium">{$i18n.t('Archive')}</div>
			</button>

			<button
				draggable="false"
				class="flex h-10 w-full cursor-pointer items-center gap-3 rounded-xl px-3 text-red-600 transition hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-400/10"
				on:click={() => {
					deleteHandler();
				}}
			>
				<div class="flex size-5 items-center justify-center text-red-500 dark:text-red-300">
					<GarbageBin strokeWidth="1.5" />
				</div>
				<div class="flex items-center font-medium">{$i18n.t('Delete')}</div>
			</button>
		</div>
	</div>
</Dropdown>
