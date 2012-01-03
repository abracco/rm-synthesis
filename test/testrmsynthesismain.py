import os, unittest, shutil
from rmsynthesis.rmsynthesismain import *
import pyfits

from numpy import arange, complex128, exp, float32, newaxis, ones, pi

class RmSynthesisTest(unittest.TestCase):
    def setUp(self):
        self.test_dir       = 'testdata'
        self.freq_filename  = os.path.join(self.test_dir, 'frequencies.txt')
        self.freq_filename_parse_error = os.path.join(self.test_dir, 'frequencies-parse-error.txt')
        self.does_not_exist = os.path.join(self.test_dir, 'does-not-exist.txt')
        self.qname = os.path.join(self.test_dir, 'Q_Fthinsource.fits')
        self.uname = os.path.join(self.test_dir, 'U_Fthinsource.fits')

        self.freq = arange(100)*10e6 +300e6
        self.phi  = arange(-100.0, 100.0, 4.0)


    def test_file_exists(self):
        self.assertTrue(file_exists(self.freq_filename))
        self.assertFalse(file_exists(self.does_not_exist))
        self.assertFalse(file_exists(self.does_not_exist, verbose=True))


    def test_parse_frequency_file(self):
        for from_file, reference in zip(parse_frequency_file(self.freq_filename),
                                        [314.159265e6, 314.359265e6, 320e6, 330e6,
                                         340000000, 350e6, 3.6e8, 3.7e8,]):
            self.assertAlmostEquals(from_file, reference)

        self.assertRaises(ParseError, lambda : parse_frequency_file(self.freq_filename_parse_error))


    def test_as_wavelength_squared(self):
        self.assertAlmostEquals(as_wavelength_squared(299792458.0), 1.0)
        map(self.assertAlmostEquals, as_wavelength_squared(array([299792458.0, 299792458.0/2.0, 299792458.0/2.0])), [1.0, 4.0, 4.0])
        empty = as_wavelength_squared(array([]))
        self.assertEquals(len(empty), 0)


    def test_get_fits_header(self):
        qheader = get_fits_header(self.qname)
        uheader = get_fits_header(self.uname)
        self.assertEquals(qheader['POL'].strip(), 'Q')
        self.assertEquals(qheader['NAXIS'], 3)
        self.assertAlmostEquals(qheader['CDELT1'], 1.3e+6)
        self.assertEquals(uheader['POL'].strip(), 'U')
        self.assertRaises(IOError, lambda : get_fits_header(self.does_not_exist))
        self.assertRaises(IOError, lambda : get_fits_header(self.freq_filename))


    def test_get_fits_header_data(self):
        hdr_q, data_q = get_fits_header_data(self.qname)
        self.assertEquals(type(hdr_q), type(pyfits.Header()))
        self.assertEquals(type(data_q), type(array([], dtype='>f4')))
        self.assertEquals(data_q.dtype, '>f4')
        self.assertEquals(len(data_q.shape), 3)
        self.assertEquals(data_q.shape, (100, 100, 100))

        self.assertRaises(IOError, lambda : get_fits_header_data(self.does_not_exist))
        self.assertRaises(IOError, lambda : get_fits_header_data(self.freq_filename))


    def test_rmsynthesis_phases(self):
        self.assertAlmostEquals(rmsynthesis_phases(1.0, pi), 1.0)
        self.assertAlmostEquals(rmsynthesis_phases(pi, 0.5), -1.0)
        map(self.assertAlmostEquals,
            rmsynthesis_phases(array([pi, 0.5*pi]), 0.5),
            [-1.0, -1j])
        map(self.assertAlmostEquals,
            rmsynthesis_phases(pi, array([0.5, -0.25])),
            [-1.0, +1j])

    

    def test_rmsynthesis_dirty(self):
        f_phi = zeros((len(self.phi)), dtype = complex64)
        f_phi[15] = 3-4j

        p_f = (f_phi[newaxis, :]*exp(2j*as_wavelength_squared(self.freq)[:, newaxis]*self.phi[newaxis, :])).sum(axis = 1)

        qcube = zeros((len(self.freq), 5, 7), dtype = complex64)
        ucube = zeros((len(self.freq), 5, 7), dtype = complex64)
        qcube[:, 2, 3] = p_f.real
        ucube[:, 2, 3] = p_f.imag

        rmcube     = rmsynthesis_dirty(qcube, ucube, self.freq, self.phi)
        rmcube_cut = rmcube.copy()
        rmcube_cut[:, 2, 3] *= 0.0
        self.assertTrue((rmcube_cut == 0.0).all())
        self.assertNotAlmostEquals(rmcube[:, 2, 3].mean(), 0.0)
        self.assertAlmostEquals(rmcube[15, 2, 3],
                                (3-4j)*exp(2j*self.phi[15]*as_wavelength_squared(self.freq).mean()),
                                places = 6)
        self.assertEquals(list(rmcube[:, 2, 3] == rmcube.max()).index(True), 15)


    def test_compute_rmsf(self):
        rmsf   = compute_rmsf(self.freq, self.phi)
        wl_m   = as_wavelength_squared(self.freq)
        wl0_m  = wl_m.mean()
        map(self.assertAlmostEquals,
            rmsf,
            exp(-2j*self.phi[newaxis, :]*(wl_m - wl0_m)[:, newaxis]).mean(axis = 0))



    def test_add_phi_to_fits_header(self):
        head = pyfits.Header()
        head.update('SIMPLE', True)
        head.update('BITPIX', -32)
        head.update('NAXIS', 3)
        head.update('NAXIS1', 1)
        head.update('NAXIS2', 1)

        head_phi = add_phi_to_fits_header(head, [-10.0, -8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0])
        self.assertEquals(head_phi['NAXIS3'], 8)
        self.assertEquals(head_phi['CTYPE3'], 'Faraday depth')
        self.assertEquals(head_phi['CUNIT3'], 'rad m^{-2}')
        self.assertAlmostEquals(head_phi['CRPIX3'], 1.0)
        self.assertAlmostEquals(head_phi['CRVAL3'], -10)
        self.assertAlmostEquals(head_phi['CDELT3'], +2.0)

        self.assertRaises(KeyError, lambda: head['NAXIS3'])
        self.assertEquals(type(add_phi_to_fits_header(head, [-10.0, -8.0])), type(pyfits.Header()))
        
        self.assertRaises(ShapeError, lambda: add_phi_to_fits_header(head, [-10.0]))
        self.assertRaises(ShapeError, lambda: add_phi_to_fits_header(head, []))


    def test_write_fits_cube(self):
        fits_name = os.tempnam()+'.fits'
        try:
            data_array_out = ones((10, 5, 7), dtype = float32)*arange(10)[:, newaxis, newaxis]
            header_out     = pyfits.Header()

            self.assertRaises(pyfits.VerifyError, lambda: write_fits_cube(data_array_out, header_out, fits_name))
            self.assertFalse(file_exists(fits_name))

            header_out.update('SIMPLE', True)
            header_out.update('BITPIX', -32)
            header_out.update('NAXIS', 3)
            header_out.update('NAXIS1', 7)
            header_out.update('NAXIS2', 5)
            header_out.update('NAXIS3', 10)
            write_fits_cube(data_array_out, header_out, fits_name)
            self.assertTrue(file_exists(fits_name))

            hdr, data = get_fits_header_data(fits_name)
            self.assertAlmostEquals(data.sum(), 5*7*arange(10).sum())
            self.assertAlmostEquals((data_array_out - data).sum(), 0.0)

            self.assertRaises(IOError,
                              lambda: write_fits_cube(data_array_out, header_out, fits_name))
            write_fits_cube(data_array_out*2, header_out, fits_name, force_overwrite = True)
            hdr2, data2 = get_fits_header_data(fits_name)
            self.assertAlmostEquals(data2.sum(), 5*7*arange(10).sum()*2)
            self.assertAlmostEquals((data_array_out*2 - data2).sum(), 0.0)
        finally: # cleanup after potential exceptions
            if file_exists(fits_name):
                os.remove(fits_name)



    def test_write_rmcube(self):
        output_dir = os.tempnam()
        os.mkdir(output_dir)
        try:
            header_out = pyfits.Header()
            header_out.update('SIMPLE', True)
            header_out.update('BITPIX', -32)
            header_out.update('NAXIS', 3)
            header_out.update('NAXIS1', 7)
            header_out.update('NAXIS2', 5)
            header_out.update('NAXIS3', 10)

            rmcube = (3.0-4.0j)*ones((10, 5, 7), dtype = complex128)
            self.assertRaises(IOError,
                              lambda: write_rmcube(rmcube, header_out,
                                                   output_dir+'no-existent',
                                                   force_overwrite = False))
            write_rmcube(rmcube, header_out, output_dir, force_overwrite = False)
            file_names = os.listdir(output_dir)
            self.assertEquals(len(file_names), 3)
            self.assertTrue('p-rmcube-dirty.fits' in file_names)
            self.assertTrue('q-rmcube-dirty.fits' in file_names)
            self.assertTrue('u-rmcube-dirty.fits' in file_names)

            hdr_p, data_p = get_fits_header_data(os.path.join(output_dir, 'p-rmcube-dirty.fits'))
            hdr_q, data_q = get_fits_header_data(os.path.join(output_dir, 'q-rmcube-dirty.fits'))
            hdr_u, data_u = get_fits_header_data(os.path.join(output_dir, 'u-rmcube-dirty.fits'))

            self.assertEquals(hdr_p['POL'], 'P')
            self.assertEquals(hdr_q['POL'], 'Q')
            self.assertEquals(hdr_u['POL'], 'U')

            self.assertEquals(data_p.shape, (10, 5, 7))
            self.assertAlmostEquals((data_p-5.0).sum(), 0.0)
            self.assertAlmostEquals((data_p-5.0).std(), 0.0)

            self.assertEquals(data_q.shape, (10, 5, 7))
            self.assertAlmostEquals((data_q-3.0).sum(), 0.0)
            self.assertAlmostEquals((data_q-3.0).std(), 0.0)

            self.assertEquals(data_u.shape, (10, 5, 7))
            self.assertAlmostEquals((data_u+4.0).sum(), 0.0)
            self.assertAlmostEquals((data_u+4.0).std(), 0.0)
            
        finally:
            shutil.rmtree(output_dir)
 

    def test_write_rmsf(self):
        output_dir = os.tempnam()
        os.mkdir(output_dir)
        try:
            rmsf  = compute_rmsf(self.freq, self.phi)
            fname = os.path.join(output_dir, 'rmsf.txt')
            write_rmsf(self.phi, rmsf, output_dir)
            self.assertTrue(file_exists(fname))
            lines    = open(fname).readlines()
            contents = array([map(float, l.split()) for l in lines])
            phi_in   = contents[:, 0]
            rmsf_in  = contents[:, 1]+1j*contents[:, 2]

            self.assertTrue(abs(phi_in-self.phi).mean()< 0.0001)
            self.assertTrue(abs(phi_in-self.phi).std() < 0.0001)

            self.assertTrue(abs(rmsf_in-rmsf).mean()< 0.0001)
            self.assertTrue(abs(rmsf_in-rmsf).std()< 0.0001)

        finally:
            shutil.rmtree(output_dir)

    

if __name__ == '__main__':
    unittest.main()
