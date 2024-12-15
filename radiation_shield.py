import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from tqdm import tqdm
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.lines import Line2D
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

class NuclearBlastShieldSimulation:
    def __init__(self):
        # Fiziksel sabitler
        self.e = 1.602e-19  # Elektron yükü [C]
        self.m_e = 9.109e-31  # Elektron kütlesi [kg]
        self.m_p = 1.672e-27  # Proton kütlesi [kg]
        self.c = 2.998e8  # Işık hızı [m/s]
        
        # Patlama parametreleri
        self.blast_yield = 20e3  # 20 kiloton TNT
        self.blast_position = np.array([0., 0., 0.])
        self.blast_radius = 100  # Patlama yarıçapı [m]
        
        # Manyetik kalkan parametreleri
        self.B0 = 2.0  # Maksimum manyetik alan [Tesla]
        self.shield_radius = 500  # Kalkan yarıçapı [m]
        self.shield_height = 1000  # Kalkan yüksekliği [m]
        
        # Simülasyon parametreleri
        self.dt = 1e-9  # Zaman adımı [s]
        self.num_steps = 1000
        
        # Parçacık verileri
        self.particles = []
        self.trajectories = []
    
    def magnetic_field(self, r, t=0):
        """Dipol manyetik alan modeli"""
        x, y, z = r - self.blast_position
        r_mag = np.sqrt(x**2 + y**2 + z**2)
        
        if r_mag < 1e-10:  # Çok küçük değerler için sıfır alan
            return np.zeros(3, dtype=np.float64)
        
        if r_mag < self.shield_radius:
            # İç bölgede dipol alan
            r_xy = np.sqrt(x**2 + y**2)
            
            # Normalize edilmiş koordinatlar
            x_norm = x / r_mag
            y_norm = y / r_mag
            z_norm = z / r_mag
            
            # Dipol alan bileşenleri (normalize edilmiş)
            B_r = self.B0 * (3 * z_norm * x_norm)
            B_theta = self.B0 * (3 * z_norm * y_norm)
            B_z = self.B0 * (3 * z_norm * z_norm - 1)
            
            # Mesafeye göre azalma
            scale_factor = (1 - r_mag/self.shield_radius)**2
            return scale_factor * np.array([B_r, B_theta, B_z], dtype=np.float64)
        else:
            return np.zeros(3, dtype=np.float64)
    
    def lorentz_force(self, q, v, B):
        """Lorentz kuvveti hesapla"""
        if np.all(B == 0) or q == 0:  # Manyetik alan veya yük sıfırsa kuvvet sıfır
            return np.zeros(3, dtype=np.float64)
        
        F = q * np.cross(v, B)
        
        # Kuvveti sınırla (çok büyük değerleri engelle)
        max_force = 1e10  # Newton
        force_mag = np.linalg.norm(F)
        if force_mag > max_force:
            F = F * (max_force / force_mag)
        
        return F
    
    def track_particle(self, particle):
        """Parçacık yörüngesini Euler yöntemiyle hesapla"""
        positions = np.zeros((self.num_steps, 3), dtype=np.float64)
        velocities = np.zeros((self.num_steps, 3), dtype=np.float64)
        energies = np.zeros(self.num_steps, dtype=np.float64)
        
        r = particle['position'].copy()
        v = particle['velocity'].copy()
        
        for i in range(self.num_steps):
            positions[i] = r
            velocities[i] = v
            energies[i] = 0.5 * particle['m'] * np.sum(v**2) / (1e6 * self.e)  # MeV
            
            if particle['q'] != 0:  # Yüklü parçacıklar için
                B = self.magnetic_field(r, i*self.dt)
                F = self.lorentz_force(particle['q'], v, B)
                a = F / particle['m']
                v += a * self.dt
            
            r += v * self.dt
            
            # Kalkan dışına çıktı mı?
            if np.linalg.norm(r - self.blast_position) > self.shield_radius:
                return positions[:i+1], velocities[:i+1], energies[:i+1]
        
        return positions, velocities, energies
    
    def generate_blast_particles(self, num_particles=1000):
        """Nükleer patlamadan kaynaklanan parçacıkları oluştur"""
        self.particles = []  # Önceki parçacıkları temizle
        
        # Parçacık tipleri ve özellikleri
        particle_types = {
            'alpha': {'q': 2*self.e, 'm': 4*self.m_p, 'ratio': 0.2, 'E_min': 4.0, 'E_max': 6.0},
            'beta': {'q': -self.e, 'm': self.m_e, 'ratio': 0.3, 'E_mean': 0.5},
            'neutron': {'q': 0, 'm': self.m_p, 'ratio': 0.2, 'E_mean': 2.0},
            'gamma': {'q': 0, 'm': 0, 'ratio': 0.3, 'E_mean': 1.5}
        }
        
        for ptype, props in particle_types.items():
            n_particles = int(num_particles * props['ratio'])
            
            # Her parçacık tipi için enerji dağılımı (MeV)
            if ptype == 'alpha':
                energies = np.random.uniform(props['E_min'], props['E_max'], n_particles)
            else:
                energies = np.random.exponential(props['E_mean'], n_particles)
            
            for E in energies:
                # Küresel koordinatlarda rastgele yön
                theta = np.random.uniform(0, np.pi)
                phi = np.random.uniform(0, 2*np.pi)
                
                # Birim yön vektörü
                direction = np.array([
                    np.sin(theta) * np.cos(phi),
                    np.sin(theta) * np.sin(phi),
                    np.cos(theta)
                ])
                
                # Hız hesapla
                if props['m'] > 0:
                    # Klasik kinetik enerji formülü: E = 1/2 * m * v^2
                    v_mag = np.sqrt(2 * E * 1e6 * self.e / props['m'])  # m/s
                    velocity = v_mag * direction
                else:  # Fotonlar için ışık hızı
                    velocity = self.c * direction
                
                self.particles.append({
                    'type': ptype,
                    'q': props['q'],
                    'm': props['m'],
                    'energy': E,  # MeV
                    'position': self.blast_position.copy(),
                    'velocity': velocity
                })
    
    def run_simulation(self, progress_callback=None):
        """Simülasyonu çalıştır ve parçacık yörüngelerini hesapla"""
        self.trajectories = []  # Önceki yörüngeleri temizle
        
        print("Nükleer patlama parçacıkları oluşturuluyor...")
        self.generate_blast_particles()
        
        print("Parçacık yörüngeleri hesaplanıyor...")
        for i, particle in enumerate(tqdm(self.particles)):
            positions = []
            velocities = []
            energies = []
            
            # Başlangıç değerlerini kaydet
            position = particle['position'].copy()
            velocity = particle['velocity'].copy()
            energy = particle['energy']  # MeV cinsinden başlangıç enerjisi
            
            positions.append(position.copy())
            velocities.append(velocity.copy())
            energies.append(energy)
            
            # Parçacık parametreleri
            q = particle['q']
            m = particle['m']
            ptype = particle['type']
            
            # Parçacık yörüngesini hesapla
            for step in range(self.num_steps):
                try:
                    # Manyetik alanı hesapla
                    B = self.magnetic_field(position)
                    
                    if m > 0 and q != 0:  # Yüklü parçacıklar için (alfa ve beta)
                        # Lorentz kuvvetini hesapla
                        F = self.lorentz_force(q, velocity, B)
                        
                        # İvmeyi hesapla (F = ma)
                        acceleration = F / m
                        
                        # Hız ve konumu güncelle (Euler integrasyonu)
                        velocity += acceleration * self.dt
                        
                        # Işık hızını geçmemesi için hızı sınırla
                        v_mag = np.linalg.norm(velocity)
                        if v_mag > 0.1 * self.c:  # Relativistik etkileri önlemek için %10 c ile sınırla
                            velocity = velocity * (0.1 * self.c / v_mag)
                        
                        # Kinetik enerjiyi hesapla (MeV cinsinden)
                        energy = 0.5 * m * np.sum(velocity**2) / (self.e * 1e6)
                    
                    elif m > 0 and q == 0:  # Nötronlar için
                        # Doğrusal hareket, enerji kaybı ekle
                        energy = energies[0] * np.exp(-0.01 * step)  # Basit üstel azalma
                    
                    else:  # Gamma ışınları için
                        # Doğrusal hareket, enerji sabit
                        energy = energies[0]
                    
                    # Konumu güncelle
                    position += velocity * self.dt
                    
                    # Yörünge verilerini kaydet
                    positions.append(position.copy())
                    velocities.append(velocity.copy())
                    energies.append(energy)
                    
                    # Kalkan dışına çıktıysa veya çok yavaşladıysa döngüyü sonlandır
                    r = np.sqrt(np.sum(position**2))
                    if r > self.shield_radius * 1.5 or energy < 0.01 * energies[0]:
                        break
                    
                except Exception as e:
                    print(f"Adım {step} hesaplanırken hata: {str(e)}")
                    break
            
            # Yörüngeyi kaydet
            if len(positions) > 1:  # En az iki nokta varsa kaydet
                self.trajectories.append({
                    'type': ptype,
                    'positions': np.array(positions),
                    'velocities': np.array(velocities),
                    'energies': np.array(energies)
                })
            
            # İlerleme durumunu bildir
            if progress_callback:
                progress = (i + 1) / len(self.particles) * 70 + 30  # 30-100 arası
                progress_callback(progress)
    
    def visualize_results(self):
        """Simülasyon sonuçlarını görselleştir"""
        fig = plt.figure(figsize=(20, 15))
        
        # 3D yörünge grafiği
        ax1 = fig.add_subplot(221, projection='3d')
        colors = {'alpha': 'red', 'beta': 'blue', 'neutron': 'green', 'gamma': 'yellow'}
        
        for traj in self.trajectories[::10]:  # Her 10 yörüngeden birini çiz
            ax1.plot(traj['positions'][:,0], traj['positions'][:,1], traj['positions'][:,2],
                    color=colors[traj['type']], alpha=0.5, label=traj['type'])
        
        # Kalkan sınırlarını çiz
        u = np.linspace(0, 2*np.pi, 100)
        v = np.linspace(-self.shield_height/2, self.shield_height/2, 100)
        U, V = np.meshgrid(u, v)
        X = self.shield_radius * np.cos(U)
        Y = self.shield_radius * np.sin(U)
        Z = V
        ax1.plot_surface(X, Y, Z, alpha=0.1, color='gray')
        
        ax1.set_title("Parçacık Yörüngeleri")
        ax1.legend()
        
        # Manyetik alan yoğunluğu haritası
        ax2 = fig.add_subplot(222)
        x = np.linspace(-self.shield_radius, self.shield_radius, 50)
        y = np.linspace(-self.shield_radius, self.shield_radius, 50)
        X, Y = np.meshgrid(x, y)
        B_strength = np.zeros_like(X)
        
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                B = self.magnetic_field(np.array([X[i,j], Y[i,j], 0]))
                B_strength[i,j] = np.linalg.norm(B)
        
        plt.imshow(B_strength, extent=[-self.shield_radius, self.shield_radius, 
                                     -self.shield_radius, self.shield_radius])
        plt.colorbar(label='Manyetik Alan Şiddeti (T)')
        ax2.set_title("Manyetik Alan Yoğunluğu")
        
        plt.tight_layout()
        return fig

    def visualize_comparative_results(self):
        """Karşılaştırmalı sonuçları görselleştir"""
        fig = plt.figure(figsize=(15, 10))
        
        # Parçacık tiplerine göre renk ve etiketler
        colors = {'alpha': 'red', 'beta': 'blue', 'neutron': 'green', 'gamma': 'yellow'}
        labels = {'alpha': 'Alfa', 'beta': 'Beta', 'neutron': 'Nötron', 'gamma': 'Gama'}
        
        # Penetrasyon derinliği dağılımı
        ax1 = fig.add_subplot(221)
        for i, (ptype, color) in enumerate(colors.items()):
            depths = []
            for traj in self.trajectories:
                if traj['type'] == ptype:
                    positions = np.array(traj['positions'])
                    if len(positions) > 0:
                        # Merkeze olan maksimum uzaklığı hesapla
                        distances = np.sqrt(np.sum(positions**2, axis=1))
                        max_depth = np.max(distances)
                        depths.append(max_depth)
            
            if depths:  # Veri varsa
                # Çubuk grafik kullan
                ax1.bar(i, np.mean(depths), alpha=0.5, color=color, 
                       label=labels[ptype], yerr=np.std(depths) if len(depths) > 1 else 0)
        
        ax1.set_xticks(range(len(colors)))
        ax1.set_xticklabels(labels.values())
        ax1.set_xlabel('Parçacık Tipi')
        ax1.set_ylabel('Ortalama Penetrasyon Derinliği (m)')
        ax1.set_title('Penetrasyon Derinliği Analizi')
        ax1.legend()
        
        # Enerji kaybı dağılımı
        ax2 = fig.add_subplot(222)
        for i, (ptype, color) in enumerate(colors.items()):
            energy_loss = []
            for traj in self.trajectories:
                if traj['type'] == ptype and len(traj['energies']) > 1:
                    initial_E = traj['energies'][0]
                    final_E = traj['energies'][-1]
                    if initial_E > 0:
                        loss = (initial_E - final_E) / initial_E * 100
                        if 0 <= loss <= 100:
                            energy_loss.append(loss)
            
            if energy_loss:  # Veri varsa
                # Çubuk grafik kullan
                ax2.bar(i, np.mean(energy_loss), alpha=0.5, color=color,
                       label=labels[ptype], yerr=np.std(energy_loss) if len(energy_loss) > 1 else 0)
        
        ax2.set_xticks(range(len(colors)))
        ax2.set_xticklabels(labels.values())
        ax2.set_xlabel('Parçacık Tipi')
        ax2.set_ylabel('Ortalama Enerji Kaybı (%)')
        ax2.set_title('Enerji Kaybı Analizi')
        ax2.legend()
        
        # Yörünge uzunluğu dağılımı
        ax3 = fig.add_subplot(223)
        for i, (ptype, color) in enumerate(colors.items()):
            path_lengths = []
            for traj in self.trajectories:
                if traj['type'] == ptype and len(traj['positions']) > 1:
                    positions = np.array(traj['positions'])
                    segments = np.diff(positions, axis=0)
                    length = np.sum(np.sqrt(np.sum(segments**2, axis=1)))
                    if length > 0:
                        path_lengths.append(length)
            
            if path_lengths:  # Veri varsa
                # Çubuk grafik kullan
                ax3.bar(i, np.mean(path_lengths), alpha=0.5, color=color,
                       label=labels[ptype], yerr=np.std(path_lengths) if len(path_lengths) > 1 else 0)
        
        ax3.set_xticks(range(len(colors)))
        ax3.set_xticklabels(labels.values())
        ax3.set_xlabel('Parçacık Tipi')
        ax3.set_ylabel('Ortalama Yörünge Uzunluğu (m)')
        ax3.set_title('Yörünge Uzunluğu Analizi')
        ax3.legend()
        
        # Saçılma açısı dağılımı
        ax4 = fig.add_subplot(224)
        for i, (ptype, color) in enumerate(colors.items()):
            scatter_angles = []
            for traj in self.trajectories:
                if traj['type'] == ptype and len(traj['positions']) > 2:
                    try:
                        positions = np.array(traj['positions'])
                        initial_dir = positions[1] - positions[0]
                        final_dir = positions[-1] - positions[-2]
                        
                        initial_norm = np.linalg.norm(initial_dir)
                        final_norm = np.linalg.norm(final_dir)
                        
                        if initial_norm > 0 and final_norm > 0:
                            initial_dir = initial_dir / initial_norm
                            final_dir = final_dir / final_norm
                            cos_angle = np.clip(np.dot(initial_dir, final_dir), -1.0, 1.0)
                            angle = np.degrees(np.arccos(cos_angle))
                            scatter_angles.append(angle)
                    except Exception as e:
                        print(f"Açı hesaplama hatası: {str(e)}")
                        continue
            
            if scatter_angles:  # Veri varsa
                # Çubuk grafik kullan
                ax4.bar(i, np.mean(scatter_angles), alpha=0.5, color=color,
                       label=labels[ptype], yerr=np.std(scatter_angles) if len(scatter_angles) > 1 else 0)
        
        ax4.set_xticks(range(len(colors)))
        ax4.set_xticklabels(labels.values())
        ax4.set_xlabel('Parçacık Tipi')
        ax4.set_ylabel('Ortalama Saçılma Açısı (derece)')
        ax4.set_title('Saçılma Açısı Analizi')
        ax4.legend()
        
        plt.tight_layout()
        return fig

    def visualize_detailed_3d_results(self):
        """3D detaylı sonuçları görselleştir"""
        fig = plt.figure(figsize=(15, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # Parçacık tiplerine göre renk ve etiketler
        colors = {'alpha': 'red', 'beta': 'blue', 'neutron': 'green', 'gamma': 'yellow'}
        labels = {'alpha': 'Alfa', 'beta': 'Beta', 'neutron': 'Nötron', 'gamma': 'Gama'}
        
        # Her parçacık tipinin yörüngelerini çiz
        for ptype in colors:
            for traj in self.trajectories:
                if traj['type'] == ptype:
                    positions = np.array(traj['positions'])
                    if len(positions) > 1:
                        ax.plot(positions[:,0], positions[:,1], positions[:,2],
                               color=colors[ptype], alpha=0.3, linewidth=1)
        
        # Kalkan sınırlarını çiz
        u = np.linspace(0, 2*np.pi, 50)
        v = np.linspace(-self.shield_height/2, self.shield_height/2, 50)
        U, V = np.meshgrid(u, v)
        X = self.shield_radius * np.cos(U)
        Y = self.shield_radius * np.sin(U)
        Z = V
        ax.plot_surface(X, Y, Z, alpha=0.1, color='gray')
        
        # Görünümü ayarla
        max_range = max(self.shield_radius, self.shield_height/2) * 1.2
        ax.set_xlim(-max_range, max_range)
        ax.set_ylim(-max_range, max_range)
        ax.set_zlim(-max_range, max_range)
        
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')
        ax.set_title('Parçacık Yörüngeleri ve Kalkan (3D)')
        
        # Lejant ekle
        legend_elements = [Line2D([0], [0], color=c, label=l) 
                         for ptype, (c, l) in zip(colors.keys(), zip(colors.values(), labels.values()))]
        ax.legend(handles=legend_elements)
        
        plt.tight_layout()
        return fig

    def run_multiple_simulations(self, scenarios):
        """Farklı senaryoları simüle et"""
        self.simulation_results = []
        
        for scenario in scenarios:
            # Senaryo parametrelerini ayarla
            self.B0 = scenario['B0']
            self.shield_radius = scenario['shield_radius']
            self.shield_height = scenario['shield_height']
            self.blast_yield = scenario['blast_yield']
            
            # Simülasyonu çalıştır
            print(f"\nSenaryo: B={self.B0}T, R={self.shield_radius}m, Y={self.blast_yield/1e3}kt")
            self.particles = []
            self.trajectories = []
            self.run_simulation()
            
            # Sonuçları analiz et
            results = self.analyze_scenario()
            results['parameters'] = scenario
            self.simulation_results.append(results)

    def analyze_scenario(self):
        """Tek bir senaryonun sonuçlarını analiz et"""
        results = {
            'particle_stats': {},
            'shield_effectiveness': {},
            'energy_distribution': {},
            'penetration_depth': {},
            'deflection_angles': {}
        }
        
        for particle_type in ['alpha', 'beta', 'neutron', 'gamma']:
            # İlgili parçacık tipinin yörüngelerini filtrele
            trajectories = [t for t in self.trajectories if t['type'] == particle_type]
            
            if not trajectories:
                continue
            
            # Parçacık istatistikleri
            initial_energies = [t['energies'][0] for t in trajectories]
            final_energies = [t['energies'][-1] for t in trajectories]
            
            # Kalkan etkinliği (enerji kaybı bazında)
            energy_loss = [(i-f)/i*100 for i, f in zip(initial_energies, final_energies)]
            
            # Penetrasyon derinliği
            penetration = [np.max(np.linalg.norm(t['positions'] - self.blast_position, axis=1))
                          for t in trajectories]
            
            # Sapma açıları
            initial_directions = [t['positions'][1] - t['positions'][0] for t in trajectories]
            final_directions = [t['positions'][-1] - t['positions'][-2] for t in trajectories]
            deflection = [np.arccos(np.dot(i, f)/(np.linalg.norm(i)*np.linalg.norm(f)))*180/np.pi
                         for i, f in zip(initial_directions, final_directions)]
            
            results['particle_stats'][particle_type] = {
                'count': len(trajectories),
                'avg_initial_energy': np.mean(initial_energies),
                'avg_final_energy': np.mean(final_energies)
            }
            
            results['shield_effectiveness'][particle_type] = np.mean(energy_loss)
            results['energy_distribution'][particle_type] = {
                'initial': initial_energies,
                'final': final_energies
            }
            results['penetration_depth'][particle_type] = penetration
            results['deflection_angles'][particle_type] = deflection
        
        return results

    def visualize_all_results(self):
        """Tüm sonuçları iki panel halinde göster"""
        plt.ion()  # Interaktif mod aç
        
        # İlk panel: Karşılaştırmalı sonuçlar
        fig1 = plt.figure(figsize=(20, 15))
        fig1.canvas.manager.window.wm_geometry("+0+0")  # Sol üst köşe
        self.visualize_comparative_results()
        
        # İkinci panel: Detaylı 3D sonuçlar
        fig2 = plt.figure(figsize=(20, 20))
        fig2.canvas.manager.window.wm_geometry("+1000+0")  # Sağ üst köşe
        self.visualize_detailed_3d_results()
        
        # Grafikleri ekranda tut
        plt.show(block=True)

class SimulationControlPanel:
    def __init__(self, simulation):
        self.sim = simulation
        self.root = tk.Tk()
        self.root.title("Radyasyon Kalkanı Simülasyonu")
        self.root.geometry("500x800+0+0")
        
        # Stil ayarları
        self.setup_styles()
        
        # Simülasyon durumu
        self.simulation_ready = False
        self.parameters_valid = False
        
        # Kontrol paneli bileşenleri
        self.create_widgets()
        
        # Grafik pencereleri
        self.comparative_window = None
        self.detailed_window = None
        self.animation_running = False
        
        # İpuçları için tooltip
        self.tooltip = None
    
    def setup_styles(self):
        """Arayüz stillerini ayarla"""
        style = ttk.Style()
        style.configure('Title.TLabel', 
                       font=('Helvetica', 14, 'bold'),
                       padding=10)
        style.configure('Header.TLabel',
                       font=('Helvetica', 12, 'bold'),
                       padding=5)
        style.configure('Info.TLabel',
                       font=('Helvetica', 10, 'italic'),
                       foreground='navy')
        style.configure('Warning.TLabel',
                       font=('Helvetica', 10),
                       foreground='red')
        style.configure('Success.TLabel',
                       font=('Helvetica', 10),
                       foreground='green')
        style.configure('Primary.TButton',
                       font=('Helvetica', 10, 'bold'),
                       padding=5)
        style.configure('Secondary.TButton',
                       font=('Helvetica', 10),
                       padding=5)
    
    def create_widgets(self):
        """Arayüz bileşenlerini oluştur"""
        # Ana container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Başlık
        title = ttk.Label(main_container, 
                         text="Radyasyon Kalkanı Simülasyonu",
                         style='Title.TLabel')
        title.pack(fill='x')
        
        # Adım adım ilerleme
        steps_frame = ttk.LabelFrame(main_container, text="Simülasyon Adımları")
        steps_frame.pack(fill='x', pady=5)
        
        self.step_vars = []
        steps = [
            "1. Parametreleri Ayarla",
            "2. Simülasyonu Çalıştır",
            "3. Sonuçları Görüntüle"
        ]
        
        for step in steps:
            var = tk.BooleanVar(value=False)
            self.step_vars.append(var)
            ttk.Checkbutton(steps_frame, text=step, variable=var, 
                           state='disabled').pack(anchor='w', padx=5)
        
        # Parametre girişleri
        param_frame = ttk.LabelFrame(main_container, text="Simülasyon Parametreleri")
        param_frame.pack(fill='x', pady=5)
        
        # Grid layout için
        param_frame.columnconfigure(1, weight=1)
        
        # Manyetik alan
        row = 0
        ttk.Label(param_frame, text="Manyetik Alan (Tesla):", 
                 style='Info.TLabel').grid(row=row, column=0, padx=5, pady=2, sticky='w')
        self.B0_var = tk.StringVar(value=str(self.sim.B0))
        self.B0_entry = ttk.Entry(param_frame, textvariable=self.B0_var)
        self.B0_entry.grid(row=row, column=1, padx=5, pady=2, sticky='ew')
        ttk.Label(param_frame, text="(0.1 - 10.0)", 
                 style='Info.TLabel').grid(row=row, column=2, padx=5, pady=2)
        
        # Kalkan yarıçapı
        row += 1
        ttk.Label(param_frame, text="Kalkan Yarıçapı (m):", 
                 style='Info.TLabel').grid(row=row, column=0, padx=5, pady=2, sticky='w')
        self.radius_var = tk.StringVar(value=str(self.sim.shield_radius))
        self.radius_entry = ttk.Entry(param_frame, textvariable=self.radius_var)
        self.radius_entry.grid(row=row, column=1, padx=5, pady=2, sticky='ew')
        ttk.Label(param_frame, text="(100 - 1000)", 
                 style='Info.TLabel').grid(row=row, column=2, padx=5, pady=2)
        
        # Patlama gücü
        row += 1
        ttk.Label(param_frame, text="Patlama Gücü (kiloton TNT):", 
                 style='Info.TLabel').grid(row=row, column=0, padx=5, pady=2, sticky='w')
        self.yield_var = tk.StringVar(value=str(self.sim.blast_yield/1e3))
        self.yield_entry = ttk.Entry(param_frame, textvariable=self.yield_var)
        self.yield_entry.grid(row=row, column=1, padx=5, pady=2, sticky='ew')
        ttk.Label(param_frame, text="(1 - 100)", 
                 style='Info.TLabel').grid(row=row, column=2, padx=5, pady=2)
        
        # Parçacık sayısı
        row += 1
        ttk.Label(param_frame, text="Parçacık Sayısı:", 
                 style='Info.TLabel').grid(row=row, column=0, padx=5, pady=2, sticky='w')
        self.particle_count_var = tk.StringVar(value="1000")
        self.particle_entry = ttk.Entry(param_frame, textvariable=self.particle_count_var)
        self.particle_entry.grid(row=row, column=1, padx=5, pady=2, sticky='ew')
        ttk.Label(param_frame, text="(100 - 5000)", 
                 style='Info.TLabel').grid(row=row, column=2, padx=5, pady=2)
        
        # Parametre doğrulama butonu
        validate_btn = ttk.Button(param_frame, text="Parametreleri Doğrula",
                                 command=self.validate_parameters,
                                 style='Primary.TButton')
        validate_btn.grid(row=row+1, column=0, columnspan=3, pady=10)
        
        # Simülasyon kontrolü
        sim_frame = ttk.LabelFrame(main_container, text="Simülasyon Kontrolü")
        sim_frame.pack(fill='x', pady=5)
        
        ttk.Button(sim_frame, text="Simülasyonu Başlat",
                  command=self.run_simulation,
                  style='Primary.TButton').pack(fill='x', padx=5, pady=5)
        
        # Görselleştirme kontrolü
        viz_frame = ttk.LabelFrame(main_container, text="Görselleştirme")
        viz_frame.pack(fill='x', pady=5)
        
        ttk.Button(viz_frame, text="3D Görünüm",
                  command=self.show_3d_view,
                  style='Secondary.TButton').pack(fill='x', padx=5, pady=2)
        ttk.Button(viz_frame, text="Analiz Grafikleri",
                  command=self.show_analysis,
                  style='Secondary.TButton').pack(fill='x', padx=5, pady=2)
        
        # Animasyon kontrolü
        anim_frame = ttk.LabelFrame(main_container, text="Animasyon")
        anim_frame.pack(fill='x', pady=5)
        
        self.anim_btn = ttk.Button(anim_frame, text="Animasyonu Başlat",
                                  command=self.toggle_animation,
                                  style='Secondary.TButton')
        self.anim_btn.pack(fill='x', padx=5, pady=5)
        
        # Durum göstergesi
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill='x', pady=5)
        
        self.status_var = tk.StringVar(value="Hazır")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                     style='Info.TLabel')
        self.status_label.pack(side='left')
        
        # İlerleme çubuğu
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_container, 
                                           variable=self.progress_var,
                                           maximum=100)
        self.progress_bar.pack(fill='x', pady=5)
        
        # Çıkış butonu
        ttk.Button(main_container, text="Çıkış",
                  command=self.quit_application,
                  style='Secondary.TButton').pack(pady=10)
    
    def toggle_animation(self):
        self.animation_running = not self.animation_running
        if self.animation_running:
            self.animate_particles()
    
    def animate_particles(self):
        if not self.animation_running:
            return
        
        try:
            if self.detailed_window is not None:
                # Mevcut figürü temizle
                plt.clf()
                
                # 3D görünüm oluştur
                ax = plt.gca(projection='3d')
                
                # Parçacık yörüngelerini çiz
                for traj in self.sim.trajectories[::5]:
                    positions = traj['positions']
                    if len(positions) > 0:  # Boş yörüngeleri kontrol et
                        color = 'red' if traj['type'] == 'alpha' else 'blue'
                        ax.plot(positions[:,0], positions[:,1], positions[:,2],
                               color=color, alpha=0.3)
                
                # Kalkan sınırlarını çiz
                u = np.linspace(0, 2*np.pi, 50)
                v = np.linspace(-self.sim.shield_height/2, self.sim.shield_height/2, 50)
                U, V = np.meshgrid(u, v)
                X = self.sim.shield_radius * np.cos(U)
                Y = self.sim.shield_radius * np.sin(U)
                Z = V
                ax.plot_surface(X, Y, Z, alpha=0.1, color='gray')
                
                # Görünümü ayarla
                ax.set_xlabel('X (m)')
                ax.set_ylabel('Y (m)')
                ax.set_zlabel('Z (m)')
                ax.set_title("Parçacık Yörüngeleri (Canlı)")
                
                plt.draw()
                plt.pause(0.1)
                
                # Bir sonraki frame için zamanlayıcı ayarla
                self.root.after(100, self.animate_particles)
                
        except Exception as e:
            print(f"Animasyon hatası: {str(e)}")
            self.animation_running = False
    
    def save_results(self):
        try:
            # Sonuçları kaydet
            import json
            import datetime
            
            results = {
                'parameters': {
                    'B0': self.sim.B0,
                    'shield_radius': self.sim.shield_radius,
                    'blast_yield': self.sim.blast_yield
                },
                'particle_stats': {},
                'effectiveness': {}
            }
            
            # statistikleri topla
            for traj in self.sim.trajectories:
                ptype = traj['type']
                if ptype not in results['particle_stats']:
                    results['particle_stats'][ptype] = {
                        'count': 0,
                        'avg_energy_loss': 0
                    }
                
                results['particle_stats'][ptype]['count'] += 1
                energy_loss = (traj['energies'][0] - traj['energies'][-1]) / traj['energies'][0] * 100
                results['particle_stats'][ptype]['avg_energy_loss'] += energy_loss
            
            # Ortalamaları hesapla
            for ptype in results['particle_stats']:
                count = results['particle_stats'][ptype]['count']
                if count > 0:
                    results['particle_stats'][ptype]['avg_energy_loss'] /= count
            
            # Dosyaya kaydet
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"simulation_results_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(results, f, indent=4)
            
            self.status_var.set(f"Sonuçlar kaydedildi: {filename}")
            
        except Exception as e:
            tk.messagebox.showerror("Hata", f"Sonuçlar kaydedilirken hata oluştu: {str(e)}")
    
    def rerun_simulation(self):
        try:
            # Parametreleri güncelle
            self.sim.B0 = float(self.B0_var.get())
            self.sim.shield_radius = float(self.radius_var.get())
            self.sim.blast_yield = float(self.yield_var.get()) * 1e3
            particle_count = int(self.particle_count_var.get())
            
            # Durum güncelle
            self.status_var.set("Simülasyon çalışıyor...")
            self.root.update()
            
            # Simülasyonu yeniden çalıştır
            self.sim.particles = []
            self.sim.trajectories = []
            self.sim.generate_blast_particles(particle_count)
            self.sim.run_simulation()
            
            # Grafikleri güncelle
            if self.comparative_window:
                self.comparative_window.destroy()
                self.comparative_window = None
            if self.detailed_window:
                self.detailed_window.destroy()
                self.detailed_window = None
            
            self.show_all()
            self.status_var.set("Simülasyon tamamlandı")
            
        except ValueError:
            tk.messagebox.showerror("Hata", "Lütfen geçerli sayısal değerler girin!")
        except Exception as e:
            tk.messagebox.showerror("Hata", f"Simülasyon çalıştırılırken hata oluştu: {str(e)}")
    
    def show_comparative(self):
        if self.comparative_window is None:
            self.comparative_window = tk.Toplevel(self.root)
            self.comparative_window.title("Karşılaştırmalı Sonuçlar")
            self.comparative_window.geometry("1000x800+300+0")
            
            fig = self.sim.visualize_comparative_results()
            
            canvas = FigureCanvasTkAgg(fig, master=self.comparative_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Toolbar ekle
            toolbar = NavigationToolbar2Tk(canvas, self.comparative_window)
            toolbar.update()
    
    def show_detailed(self):
        if self.detailed_window is None:
            self.detailed_window = tk.Toplevel(self.root)
            self.detailed_window.title("3D Detaylı Analiz")
            self.detailed_window.geometry("1000x800+300+0")
            
            fig = self.sim.visualize_detailed_3d_results()
            
            canvas = FigureCanvasTkAgg(fig, master=self.detailed_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Toolbar ekle
            toolbar = NavigationToolbar2Tk(canvas, self.detailed_window)
            toolbar.update()
    
    def show_3d_view(self):
        """3D görünümü göster"""
        if not self.simulation_ready:
            tk.messagebox.showwarning("Uyarı", "Önce simülasyonu çalıştırın!")
            return
            
        try:
            if self.detailed_window is None:
                self.detailed_window = tk.Toplevel(self.root)
                self.detailed_window.title("3D Parçacık Yörüngeleri")
                self.detailed_window.geometry("1000x800+300+0")
                
                fig = plt.figure(figsize=(12, 10))
                ax = fig.add_subplot(111, projection='3d')
                
                # Parçacık yörüngelerini çiz
                for traj in self.sim.trajectories:
                    positions = np.array(traj['positions'])
                    if len(positions) > 0:
                        color = {
                            'alpha': 'red',
                            'beta': 'blue',
                            'neutron': 'green',
                            'gamma': 'yellow'
                        }.get(traj['type'], 'gray')
                        
                        ax.plot(positions[:,0], positions[:,1], positions[:,2],
                               color=color, alpha=0.5, linewidth=1)
                
                # Kalkan sınırlarını çiz
                u = np.linspace(0, 2*np.pi, 50)
                v = np.linspace(-self.sim.shield_height/2, self.sim.shield_height/2, 50)
                U, V = np.meshgrid(u, v)
                X = self.sim.shield_radius * np.cos(U)
                Y = self.sim.shield_radius * np.sin(U)
                Z = V
                ax.plot_surface(X, Y, Z, alpha=0.2, color='gray')
                
                # Eksenleri ayarla
                max_range = max(self.sim.shield_radius, self.sim.shield_height/2) * 1.2
                ax.set_xlim(-max_range, max_range)
                ax.set_ylim(-max_range, max_range)
                ax.set_zlim(-max_range, max_range)
                
                ax.set_xlabel('X (m)')
                ax.set_ylabel('Y (m)')
                ax.set_zlabel('Z (m)')
                ax.set_title("Parçacık Yörüngeleri ve Kalkan")
                
                # Lejant ekle
                legend_elements = [Line2D([0], [0], color=c, label=t) 
                                 for t, c in [('Alfa', 'red'), ('Beta', 'blue'),
                                            ('Nötron', 'green'), ('Gama', 'yellow')]]
                ax.legend(handles=legend_elements, loc='upper right')
                
                canvas = FigureCanvasTkAgg(fig, master=self.detailed_window)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
                # Toolbar ekle
                toolbar = NavigationToolbar2Tk(canvas, self.detailed_window)
                toolbar.update()
                
        except Exception as e:
            tk.messagebox.showerror("Hata", f"3D görünüm oluşturulurken hata: {str(e)}")
    
    def show_all(self):
        self.show_comparative()
        self.show_detailed()
    
    def show_analysis(self):
        """Detaylı analiz grafiklerini göster"""
        if not self.simulation_ready:
            tk.messagebox.showwarning("Uyarı", "Önce simülasyonu çalıştırın!")
            return
            
        try:
            analysis_window = tk.Toplevel(self.root)
            analysis_window.title("Detaylı Analiz")
            analysis_window.geometry("1200x800+300+0")
            
            fig = plt.figure(figsize=(12, 8))
            
            # Alt grafikler için düzen oluştur
            gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
            
            # Parçacık tiplerine göre enerji dağılımı
            ax1 = fig.add_subplot(gs[0, 0])
            particle_types = {'alpha': 'Alfa', 'beta': 'Beta', 'neutron': 'Nötron', 'gamma': 'Gama'}
            colors = {'alpha': 'red', 'beta': 'blue', 'neutron': 'green', 'gamma': 'yellow'}
            
            for ptype in particle_types:
                energies = [traj['energies'][0] for traj in self.sim.trajectories if traj['type'] == ptype]
                if energies:
                    ax1.hist(energies, bins=20, alpha=0.5, label=particle_types[ptype], color=colors[ptype])
            
            ax1.set_xlabel('Başlangıç Enerjisi (MeV)')
            ax1.set_ylabel('Parçacık Sayısı')
            ax1.set_title('Parçacık Tiplerine Göre Enerji Dağılımı')
            ax1.legend()
            
            # Penetrasyon derinliği analizi
            ax2 = fig.add_subplot(gs[0, 1])
            for ptype in particle_types:
                depths = [np.max(np.sqrt(np.sum(np.array(traj['positions'])**2, axis=1))) 
                         for traj in self.sim.trajectories if traj['type'] == ptype]
                if depths:
                    ax2.hist(depths, bins=20, alpha=0.5, label=particle_types[ptype], color=colors[ptype])
            
            ax2.set_xlabel('Maksimum Penetrasyon Derinliği (m)')
            ax2.set_ylabel('Parçacık Sayısı')
            ax2.set_title('Penetrasyon Derinliği Dağılımı')
            ax2.legend()
            
            # Enerji kaybı analizi
            ax3 = fig.add_subplot(gs[1, 0])
            for ptype in particle_types:
                energy_loss = [(traj['energies'][0] - traj['energies'][-1])/traj['energies'][0] * 100
                             for traj in self.sim.trajectories if traj['type'] == ptype]
                if energy_loss:
                    ax3.hist(energy_loss, bins=20, alpha=0.5, label=particle_types[ptype], color=colors[ptype])
            
            ax3.set_xlabel('Enerji Kaybı (%)')
            ax3.set_ylabel('Parçacık Sayısı')
            ax3.set_title('Enerji Kaybı Dağılımı')
            ax3.legend()
            
            # Yörünge uzunluğu analizi
            ax4 = fig.add_subplot(gs[1, 1])
            for ptype in particle_types:
                path_lengths = []
                for traj in self.sim.trajectories:
                    if traj['type'] == ptype:
                        positions = np.array(traj['positions'])
                        if len(positions) > 1:
                            diffs = np.diff(positions, axis=0)
                            length = np.sum(np.sqrt(np.sum(diffs**2, axis=1)))
                            path_lengths.append(length)
                
                if path_lengths:
                    ax4.hist(path_lengths, bins=20, alpha=0.5, label=particle_types[ptype], color=colors[ptype])
            
            ax4.set_xlabel('Yörünge Uzunluğu (m)')
            ax4.set_ylabel('Parçacık Sayısı')
            ax4.set_title('Yörünge Uzunluğu Dağılımı')
            ax4.legend()
            
            # Canvas ve toolbar ekle
            canvas = FigureCanvasTkAgg(fig, master=analysis_window)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            toolbar = NavigationToolbar2Tk(canvas, analysis_window)
            toolbar.update()
            
            # Özet istatistikler
            stats_frame = ttk.LabelFrame(analysis_window, text="Özet İstatistikler")
            stats_frame.pack(fill='x', padx=10, pady=5)
            
            # Parçacık tiplerine göre istatistikler
            for ptype in particle_types:
                type_trajectories = [t for t in self.sim.trajectories if t['type'] == ptype]
                if type_trajectories:
                    avg_energy_loss = np.mean([(t['energies'][0] - t['energies'][-1])/t['energies'][0] * 100
                                             for t in type_trajectories])
                    max_depth = np.max([np.max(np.sqrt(np.sum(np.array(t['positions'])**2, axis=1)))
                                      for t in type_trajectories])
                    
                    stats_text = f"{particle_types[ptype]}: {len(type_trajectories)} parçacık, "
                    stats_text += f"Ort. Enerji Kaybı: {avg_energy_loss:.1f}%, "
                    stats_text += f"Maks. Derinlik: {max_depth:.1f}m"
                    
                    ttk.Label(stats_frame, text=stats_text).pack(anchor='w', padx=5, pady=2)
            
        except Exception as e:
            tk.messagebox.showerror("Hata", f"Analiz görüntülenirken hata oluştu: {str(e)}")
    
    def quit_application(self):
        if tk.messagebox.askokcancel("Çıkış", "Uygulamadan çıkmak istiyor musunuz?"):
            plt.close('all')
            self.root.quit()
            self.root.destroy()
    
    def run(self):
        self.root.mainloop()
    
    def validate_parameters(self):
        """Girilen parametreleri doğrula"""
        try:
            # Manyetik alan kontrolü
            B0 = float(self.B0_var.get())
            if not 0.1 <= B0 <= 10.0:
                raise ValueError("Manyetik alan 0.1 ile 10.0 Tesla arasında olmalıdır.")

            # Kalkan yarıçapı kontrolü
            radius = float(self.radius_var.get())
            if not 100 <= radius <= 1000:
                raise ValueError("Kalkan yarıçapı 100 ile 1000 metre arasında olmalıdır.")

            # Patlama gücü kontrolü
            blast_yield = float(self.yield_var.get())
            if not 1 <= blast_yield <= 100:
                raise ValueError("Patlama gücü 1 ile 100 kiloton arasında olmalıdır.")

            # Parçacık sayısı kontrolü
            particle_count = int(self.particle_count_var.get())
            if not 100 <= particle_count <= 5000:
                raise ValueError("Parçacık sayısı 100 ile 5000 arasında olmalıdır.")

            # Parametreler geçerliyse durumu güncelle
            self.parameters_valid = True
            self.step_vars[0].set(True)  # İlk adımı tamamla
            self.status_var.set("Parametreler geçerli")
            tk.messagebox.showinfo("Başarılı", "Parametreler doğrulandı!")

        except ValueError as e:
            self.parameters_valid = False
            self.status_var.set("Parametre hatası!")
            tk.messagebox.showerror("Hata", str(e))
        except Exception as e:
            self.parameters_valid = False
            self.status_var.set("Beklenmeyen hata!")
            tk.messagebox.showerror("Hata", f"Beklenmeyen bir hata oluştu: {str(e)}")

    def run_simulation(self):
        """Simülasyonu çalıştır ve sonuçları görüntüle"""
        if not self.parameters_valid:
            tk.messagebox.showwarning("Uyarı", "Lütfen önce parametreleri doğrulayın!")
            return

        try:
            # Parametreleri güncelle
            self.sim.B0 = float(self.B0_var.get())
            self.sim.shield_radius = float(self.radius_var.get())
            self.sim.blast_yield = float(self.yield_var.get()) * 1e3
            particle_count = int(self.particle_count_var.get())

            # Durum güncelle
            self.status_var.set("Simülasyon başlatılıyor...")
            self.progress_var.set(0)
            self.root.update()

            # Simülasyonu çalıştır
            self.sim.particles = []
            self.sim.trajectories = []
            
            def update_progress(progress):
                self.progress_var.set(progress)
                self.root.update()

            # Parçacıkları oluştur
            self.status_var.set("Parçacıklar oluşturuluyor...")
            self.sim.generate_blast_particles(particle_count)
            self.progress_var.set(30)
            self.root.update()

            # Simülasyonu çalıştır
            self.status_var.set("Yörüngeler hesaplanıyor...")
            self.sim.run_simulation(progress_callback=update_progress)
            
            # İkinci adımı tamamla
            self.step_vars[1].set(True)
            
            # Sonuçları görüntüle
            self.status_var.set("Sonuçlar görüntüleniyor...")
            self.show_all()
            
            # Üçüncü adımı tamamla
            self.step_vars[2].set(True)
            
            # Simülasyon hazır
            self.simulation_ready = True
            self.status_var.set("Simülasyon tamamlandı")
            self.progress_var.set(100)

        except Exception as e:
            self.simulation_ready = False
            self.status_var.set("Simülasyon hatası!")
            tk.messagebox.showerror("Hata", f"Simülasyon çalıştırılırken hata oluştu: {str(e)}")
            self.progress_var.set(0)

# Ana programda kullanımı güncelle
if __name__ == "__main__":
    # Simülasyonu oluştur
    sim = NuclearBlastShieldSimulation()
    
    # Kontrol panelini başlat
    control_panel = SimulationControlPanel(sim)
    control_panel.run()
