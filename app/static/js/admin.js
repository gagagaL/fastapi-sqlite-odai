async function runFullPipeline() {
    try {
        const articlesPerSite = document.getElementById('articles-per-site').value || 20;
        const formData = new FormData();
        formData.append('articles_per_site', articlesPerSite);

        showMessage('🚀 拡張パイプライン実行開始...');
        
        const response = await fetch('/api/scraping/full-pipeline-all', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        if (data.saved === 0) {
            showMessage('ℹ️ 新しい記事はありませんでした');
        } else {
            showMessage(`✅ 完了: ${data.collected}件収集, ${data.saved}件保存, ${data.words}個の単語を抽出`);
        }
        
        // 状態を更新
        await updateStats();
        
    } catch (error) {
        showMessage(`❌ エラー: ${error.message}`, 'error');
        console.error(error);
    }
}