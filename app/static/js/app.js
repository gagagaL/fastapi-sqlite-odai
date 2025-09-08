// APIの基本設定
const API_BASE = '/api';

// サンプルデータ投入
async function initSampleData() {
    try {
        const response = await fetch(`${API_BASE}/admin/init-sample-data`, {
            method: 'POST',
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(result.message);
            location.reload();
        } else {
            alert('エラーが発生しました');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('通信エラーが発生しました');
    }
}

// 新しいお題を取得
async function getNewTopic() {
    try {
        const response = await fetch(`${API_BASE}/topics/random`);
        
        if (response.ok) {
            location.reload(); // 簡単のためリロード
        } else {
            alert('新しいお題が見つかりませんでした');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('通信エラーが発生しました');
    }
}

// お題をシェア
function shareTopic() {
    const topicText = document.querySelector('.alert-light h2')
}