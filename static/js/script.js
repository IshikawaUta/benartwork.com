// Anda dapat menambahkan script JavaScript kustom di sini
document.addEventListener('DOMContentLoaded', () => {
    console.log('Website Anda siap!');

    // --- Logika Scroll to Top Button ---
    const scrollToTopBtn = document.getElementById('scrollToTopBtn');

    // Tampilkan tombol saat pengguna menggulir ke bawah 20px dari atas dokumen
    window.onscroll = function() {
        if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
            scrollToTopBtn.style.display = "block";
            scrollToTopBtn.style.opacity = "1"; // Pastikan terlihat
        } else {
            scrollToTopBtn.style.display = "none";
            scrollToTopBtn.style.opacity = "0"; // Sembunyikan dengan transisi
        }
    };

    // Saat tombol diklik, gulir ke atas dokumen dengan efek smooth
    scrollToTopBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth' // Efek gulir halus
        });
    });
});